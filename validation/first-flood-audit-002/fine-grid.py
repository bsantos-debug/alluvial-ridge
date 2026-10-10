#!/usr/bin/env python3
"""Replay completed 250 m/125 m first-flood outputs using adjacent retained files.

Native-grid and inventory calculations follow the retained terminal auditor.
The frozen model and existing time-step numerical helpers are unchanged.
"""
import sys
sys.dont_write_bytecode = True
import hashlib
import io
import json
import math
from pathlib import Path
import runpy
import struct
import tarfile
from types import SimpleNamespace

CASES = ('baseline250', 'fine125')
BINARY = 'b3d984881a2f82757ff9bb6ca7c15f9e3c28e3d34106ae477fe7c06af6f8099c'
HELPER_SHA256 = '7e304445cbc8fab0c6eb9068328d3707a9f47906ca21371c5f5b258fd0427073'
FROZEN_SOURCE_SHA256 = {
    'src/finite_volume.hpp': '57ac8606cd856046e13563fc0f07417943990fbc4f43340baf6f44aad427775d',
    'src/main.cpp': '812058d4ff97b618da08830e44a8704e4dc3a1431e0245136a301a0cd4375c90',
    'src/migration.hpp': '047475c7a53b933ccc83273e0576a820f681382fdf22b244a501006c68bf7196',
    'src/model.hpp': 'e12bb6c79a9e70ca53d555fc2d5cfcefed9b0cf2f8a3f7567defd650cc039a15',
    'src/sediment.hpp': '3c698eaf05771c09a26a152697fdcdacacf59b08ad18345efcdcaf1e35ccd4d2'}
PROVENANCE_SHA256 = '66d040d7d9a77b6725efc3d1beaa1089ae6b82df072463ed6b80210401715a94'
EXTRA_SHA256 = {
    'evidence/audit.py': '089f7083511eb9985baaa5a903f5844bb973fbd2ae4a819bd51149f34025ca43',
    'evidence/terminal.json': 'a7c108dda3877e033b42c3bc8f0b2879deb5b556712e21c1028b4386685d74af',
    'evidence/readiness.json': 'f5846cdcdb466d51222d7f34c1de14368882026b5456a9be3dd4c8172a45f6f0',
    'evidence/validation-provenance.json': '66d040d7d9a77b6725efc3d1beaa1089ae6b82df072463ed6b80210401715a94',
    'evidence/validation-manifest.json': 'f9fbf826d749847c86d4b6ce5e651751939c466d4c0634cd49f7a10bfa385cf9',
    'evidence/time-step-capture.json': 'b47e8c73d2ec99445678bb0d47614edbb021f73aba61d492581e6094135f6b5f'}
SCOPE = ('Completed first-flood floodplain-grid sensitivity, dx250 versus dx125 with '
         'common 250 m channel nodes. No spatial-convergence order, later-flood or manuscript claim.')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def parameters(blob,helper):
    p={}
    for line in blob.decode().splitlines():
        k,v=line.split(" ",1)
        if k=="command":continue
        require(k not in p,"duplicate numerical parameter: "+k)
        p[k]=float(v)
    require(set(p)==set(helper.SIGNATURE_KEYS+["floods"]) and
            all(math.isfinite(v) for v in p.values()),"invalid numerical parameters")
    return p
def field(blob,p,phase):
    """Native-grid adapter; retained field() is deliberately left unchanged."""
    require(len(blob)>=40,"truncated raster header")
    nx,ny,nodes,flood,dx,clock,slope=struct.unpack("<4i3d",blob[:40])
    ex,ey=int(p["length"]/p["dx"]),int(p["width"]/p["dx"])
    require(ex*p["dx"]==p["length"] and ey*p["dx"]==p["width"],"grid does not tile domain")
    require((nx,ny,nodes,flood,dx,clock,slope)==
            (ex,ey,289,1,p["dx"],phase*p["duration"],p["slope"]),"unexpected native raster metadata")
    require(len(blob)==40+16*nx*ny,"incorrect native raster payload length")
    cells=list(struct.iter_unpack("<4f",blob[40:]))
    require(all(all(math.isfinite(v) for v in c) and c[1]>=0 and c[2]>=0 and
                c[3] in (0,1) for c in cells),"invalid native raster state")
    return dict(nx=nx,ny=ny,channel_nodes=nodes,flood=flood,dx_m=dx,
                elapsed_seconds=clock,slope=slope),cells

def decimal12_bound(value):
    return 0. if value==0 else .5*10.**(math.floor(math.log10(abs(value)))-11)

def phase_metrics(metadata,cells,rows,p,helper):
    result=helper.snapshot(metadata,cells)
    result["field_minima"]={name:min(c[k] for c in cells) for k,name in
                            enumerate(("bed_m","water_depth_m","event_deposit_m","mask"))}
    result["field_maxima"]={name:max(c[k] for c in cells) for k,name in
                            enumerate(("bed_m","water_depth_m","event_deposit_m","mask"))}
    result["channel_depth_range_m"]=[min(r["water_depth"] for r in rows),max(r["water_depth"] for r in rows)]
    result["channel_control_area_range_m2"]=[min(r["control_area"] for r in rows),max(r["control_area"] for r in rows)]
    result["channel_water_volume_from_csv_m3"]=math.fsum(r["water_depth"]*r["control_area"] for r in rows)
    result["channel_water_csv_rounding_bound_m3"]=math.fsum(
        abs(r["control_area"])*decimal12_bound(r["water_depth"])+
        abs(r["water_depth"])*decimal12_bound(r["control_area"])+
        decimal12_bound(r["water_depth"])*decimal12_bound(r["control_area"]) for r in rows)
    result["floodplain_water_float32_storage_bound_m3"]=math.fsum(helper.half_ulp(c[1]) for c in cells if c[3]==0)*p["dx"]**2
    result["total_water_volume_from_raster_and_csv_m3"]=result["floodplain_water_volume_m3"]+result["channel_water_volume_from_csv_m3"]
    result["total_water_storage_and_csv_bound_m3"]=result["floodplain_water_float32_storage_bound_m3"]+result["channel_water_csv_rounding_bound_m3"]
    density=p["rho_s"]*(1-p["porosity"])
    result["dry_bulk_density_kg_per_m3"]=density
    result["event_deposit_mineral_mass_from_raster_kg"]=result["event_deposit_bulk_volume_m3"]*density
    result["event_deposit_mineral_mass_storage_bound_kg"]=result["event_deposit_bulk_volume_storage_bound_m3"]*density
    result["native_channel_mask_cells"]=sum(c[3]==1 for c in cells)
    return result

def compatible_fields(coarse,fine,coarse_metadata,fine_metadata,helper):
    """Area averages on common, wholly floodplain 250 m squares; no interpolation."""
    nx,ny=coarse_metadata["nx"],coarse_metadata["ny"]
    require(coarse_metadata["dx_m"]==250 and fine_metadata["dx_m"]==125 and
            fine_metadata["nx"]==2*nx and fine_metadata["ny"]==2*ny,
            "comparison grids are not aligned 2:1 refinements")
    require(len(coarse)==nx*ny and len(fine)==4*nx*ny and
            coarse_metadata["elapsed_seconds"]==fine_metadata["elapsed_seconds"] and
            coarse_metadata["flood"]==fine_metadata["flood"] and
            coarse_metadata["slope"]==fine_metadata["slope"],
            "comparison payload lengths, phase, or reference slope differ")
    pairs=[];counts={};mask_disagreement=0
    for j in range(ny):
        for i in range(nx):
            a=coarse[j*nx+i]
            children=[fine[(2*j+dj)*(2*nx)+2*i+di] for dj in (0,1) for di in (0,1)]
            fine_fp=sum(c[3]==0 for c in children)
            key=("coarse_channel" if a[3] else "coarse_floodplain")+"_fine_floodplain_children_"+str(fine_fp)
            counts[key]=counts.get(key,0)+1
            mask_disagreement+=sum(c[3]!=a[3] for c in children)
            if a[3]==0 and fine_fp==4:pairs.append((a,children))
    require(pairs,"no compatible full floodplain squares")
    out=dict(method="Fine minus baseline after averaging each aligned 2x2 fine block onto its 250 m footprint; only baseline floodplain cells whose four fine children are all floodplain. Dry cells included; mixed or differing masks excluded.",
             coarse_cells=len(pairs),common_area_m2=len(pairs)*250**2,
             excluded_coarse_cells=nx*ny-len(pairs),excluded_total_area_m2=(nx*ny-len(pairs))*250**2,
             excluded_baseline_floodplain_area_m2=(sum(c[3]==0 for c in coarse)-len(pairs))*250**2,
             mask_overlap_coarse_cell_counts=counts,
             raster_mask_disagreement_area_m2=mask_disagreement*125**2,fields={})
    for k,name in enumerate(("bed","water_depth","event_deposit")):
        delta=[math.fsum(c[k] for c in children)/4-a[k] for a,children in pairs]
        bounds=[helper.half_ulp(a[k])+math.fsum(helper.half_ulp(c[k]) for c in children)/4 for a,children in pairs]
        out["fields"][name]=dict(mean_signed_difference_m=math.fsum(delta)/len(delta),
            mean_absolute_difference_m=math.fsum(abs(v) for v in delta)/len(delta),
            maximum_absolute_difference_m=max(abs(v) for v in delta),
            mean_difference_float32_storage_bound_m=math.fsum(bounds)/len(bounds),
            maximum_difference_float32_storage_bound_m=max(bounds),
            integrated_difference_over_common_area_m3=math.fsum(delta)*250**2,
            integrated_difference_float32_storage_bound_m3=math.fsum(bounds)*250**2)
    return out
def channel(blob,helper):
    rows=helper.csv_rows(blob)
    require(len(rows)==289 and all(set(r)=={"x","y","bed","water_depth","velocity","control_area"} for r in rows),"invalid channel schema/count")
    require(all(all(math.isfinite(v) for v in r.values()) and r["water_depth"]>0 and r["control_area"]>0 for r in rows),"invalid channel physical values")
    require(rows[0]["x"]==0 and rows[-1]["x"]==72000 and all(rows[i+1]["x"]-rows[i]["x"]==250 for i in range(288)),"unexpected channel spacing")
    return rows
def decode_arrays(blob,p):
    slen=struct.unpack_from("<Q",blob)[0];at=8+slen
    h=struct.unpack_from("<idqqi4d3d5dQ",blob,at);at+=struct.calcsize("<idqqi4d3d5dQ");n=h[-1]
    def block(fmt,count):
        nonlocal at
        size=struct.calcsize("<"+fmt)*count
        result=list(struct.iter_unpack("<"+fmt,blob[at:at+size]));at+=size
        return result
    line=block("2d",n);ch=block("6d",n)
    size=int(p["length"]/p["dx"])*int(p["width"]/p["dx"])
    bed=[r[0] for r in block("d",size)];q=block("6d",size)
    require(at==len(blob),"independent payload decode length differs")
    require(all(all(math.isfinite(v) for v in r) for r in line+ch+q) and all(math.isfinite(z) for z in bed),"nonfinite array")
    require(all(r[k]>=0 for r in ch+q for k in (0,3,4,5)),"negative physical array")
    dx=p["dx"];nx=int(p["length"]/dx);ny=int(p["width"]/dx);radius=p["channel_width"]/2
    mask=[False]*size
    for a,b in zip(line,line[1:]):
        vx,vy=b[0]-a[0],b[1]-a[1];ll=vx*vx+vy*vy
        require(ll>0,"duplicate checkpoint channel nodes")
        for j in range(max(0,int(math.floor((min(a[1],b[1])-radius)/dx))),min(ny-1,int(math.floor((max(a[1],b[1])+radius)/dx)))+1):
            for i in range(max(0,int(math.floor((min(a[0],b[0])-radius)/dx))),min(nx-1,int(math.floor((max(a[0],b[0])+radius)/dx)))+1):
                px,py=(i+.5)*dx-a[0],(j+.5)*dx-a[1];w=max(0.,min(1.,(px*vx+py*vy)/ll))
                if math.hypot(px-w*vx,py-w*vy)<=radius:mask[j*nx+i]=True
    s=[0.]
    for a,b in zip(line,line[1:]):s.append(s[-1]+math.hypot(b[0]-a[0],b[1]-a[1]))
    area=[.5*(s[min(i+1,n-1)]-s[max(i-1,0)])*p["channel_width"] for i in range(n)]
    require(all(math.isfinite(a) and a>0 for a in area),"invalid reconstructed channel area")
    inventory=[math.fsum([q[i][k]*dx*dx for i in range(size) if not mask[i]]+[row[k]*a for row,a in zip(ch,area)]) for k in (0,3,4,5)]
    bed_mass=math.fsum((z-p["slope"]*(p["length"]-(i%nx+.5)*dx))*p["rho_s"]*(1-p["porosity"])*dx*dx for i,z in enumerate(bed))
    physical_minima={"channel_"+label:min(r[k] for r in ch) for k,label in ((0,"water_depth"),(3,"sand"),(4,"silt"),(5,"clay"))}
    physical_minima.update({"raster_"+label:min(r[k] for r in q) for k,label in ((0,"water_depth"),(3,"sand"),(4,"silt"),(5,"clay"))})
    return dict(inventory=inventory,bed_mass=bed_mass,mask=mask,channel_area_total=math.fsum(area),channel_area_min=min(area),channel_area_max=max(area),channel_area_identity_error=math.fsum(area)-p["channel_width"]*s[-1],physical_minima=physical_minima)


def analyse(blobs_by_case, helper):
    base, data = (blobs_by_case[name] for name in CASES)
    base_process, process = (json.loads(b['process_status.json'].decode()) for b in (base, data))
    bp, cp = parameters(base['parameters.txt'], helper), parameters(data['parameters.txt'], helper)
    differences = {k: [bp[k], cp[k]] for k in bp if bp[k] != cp[k]}
    require(differences == {'dx': [250., 125.]}, 'sole numerical change is not dx250 to dx125')
    ARTIFACTS = helper.ARTIFACTS
    cases={};phase_arrays={};phase_metadata={};geometry={}
    for name,p,blobs,rec in (("baseline250",bp,base,base_process),("fine125",cp,data,process)):
        summary=helper.one_row(blobs["summary.csv"]);remap=helper.one_row(blobs["remap_budget.csv"])
        require(all(summary[k]>=0 for k in ("water_storage","bank_mass","recycled_mass","cutoffs","steps","channel_steps")) and
                summary["channel_depth"]>0 and remap["post_water_storage"]>=0,"invalid required scalar inventory")
        phase_arrays[name]={};phase_metadata[name]={};geometry[name]={};phases={}
        for phase,fraction,prefix_file in (("peak",.6,"peak_"),("end",1.,"")):
            md,cells=field(blobs[prefix_file+"fields_0001.bin"],p,fraction)
            rows=channel(blobs[prefix_file+"channel_0001.csv"],helper)
            phases[phase]=phase_metrics(md,cells,rows,p,helper)
            phase_arrays[name][phase]=cells;phase_metadata[name][phase]=md
            geometry[name][phase]=[(r["x"],r["y"],r["control_area"]) for r in rows]
        require(geometry[name]["peak"]==geometry[name]["end"] and
                [c[3] for c in phase_arrays[name]["peak"]]==[c[3] for c in phase_arrays[name]["end"]],
                "first-flood channel geometry or native mask changed before remap")
        peak,end=phases["peak"],phases["end"]
        require(peak["alpha_storage_interval_m"][0] is not None and
                peak["alpha_storage_interval_m"][0]-decimal12_bound(summary["alpha"])<=summary["alpha"]<=
                peak["alpha_storage_interval_m"][1]+decimal12_bound(summary["alpha"]),"peak alpha differs from completed summary")
        require(abs(peak["mean_floodplain_depth_m"]-summary["mean_water"])<=
                peak["mean_depth_storage_bound_m"]+decimal12_bound(summary["mean_water"]),"peak mean depth differs from summary")
        require(peak["definitely_wet_faces"]/peak["interface_faces"]-decimal12_bound(summary["interface_fraction"])<=
                summary["interface_fraction"]<=
                peak["possibly_wet_faces"]/peak["interface_faces"]+decimal12_bound(summary["interface_fraction"]),
                "peak interface fraction differs from summary")
        end["pre_remap_water_minus_summary_m3"]=end["total_water_volume_from_raster_and_csv_m3"]-summary["water_storage"]
        require(abs(end["pre_remap_water_minus_summary_m3"])<=
                end["total_water_storage_and_csv_bound_m3"]+decimal12_bound(summary["water_storage"]),
                "end raster/channel water differs from pre-remap summary")
        cells=phase_arrays[name]["end"]
        stored=helper.checkpoint(blobs["checkpoint.bin"],p,cells)
        require(stored["steps"]==summary["steps"] and stored["channel_steps"]==summary["channel_steps"] and
                stored["steps"]>0 and stored["channel_steps"]>=stored["steps"],"checkpoint/summary counters differ")
        require(stored["recycled_mass_kg"]>=0 and stored["cutoffs"]>=0 and
                stored["water_correction_m3"]>=0 and stored["mass_correction_kg"]>=0,
                "negative required checkpoint inventory")
        require(stored["cutoffs"]>=summary["cutoffs"] and summary["cutoffs"]==int(summary["cutoffs"]),
                "cutoff counter decreased or is nonintegral")
        stored["cutoffs_added_at_first_remap"]=stored["cutoffs"]-int(summary["cutoffs"])
        arrays=decode_arrays(blobs["checkpoint.bin"],p)
        inventory=arrays.pop("inventory");mask=arrays.pop("mask");bed=arrays.pop("bed_mass")
        captured=sum(c[3]==0 and m for c,m in zip(cells,mask))
        abandoned=sum(c[3]==1 and not m for c,m in zip(cells,mask))
        require(captured==stored["captured_floodplain_cells"] and abandoned==stored["abandoned_channel_cells"],
                "independent native-grid remap event counts differ")
        stored["captured_floodplain_area_m2"]=captured*p["dx"]**2
        stored["abandoned_channel_area_m2"]=abandoned*p["dx"]**2
        external=math.fsum(stored["net_external_sediment_by_class_kg"])
        suspension_residual=math.fsum(inventory[1:])+stored["deposited_mass_kg"]-external-stored["mass_correction_kg"]
        fullsolid=bed+math.fsum(inventory[1:])+stored["bank_mass_kg"]
        reaggregation=dict(post_water_and_suspended_class_storage=inventory,
          post_water_storage_minus_ledger_m3=inventory[0]-remap["post_water_storage"],
          independently_reaggregated_suspension_plus_deposition_residual_kg=suspension_residual,
          post_suspension_plus_deposition_residual_minus_ledger_kg=suspension_residual-remap["post_sediment_residual"],
          signed_bed_inventory_relative_to_initial_plane_kg=bed,signed_post_full_solid_inventory_kg=fullsolid,
          implied_initial_water_storage_m3=inventory[0]-stored["net_external_water_m3"]-stored["water_correction_m3"]-remap["post_water_residual"],
          implied_initial_full_solid_inventory_kg=fullsolid+stored["recycled_mass_kg"]-stored["bed_forcing_mass_kg"]-external-stored["mass_correction_kg"]-remap["post_solid_sediment_residual"],
          **arrays)
        require(abs(reaggregation["post_water_storage_minus_ledger_m3"])<.001 and
                abs(reaggregation["post_suspension_plus_deposition_residual_minus_ledger_kg"])<.001,
                "independent inventory reaggregation discrepancy")
        identities=dict(water=remap["post_water_residual"]-summary["water_residual"]-remap["water_transfer_residual"],
          sediment=remap["post_sediment_residual"]-summary["sediment_residual"]-
            math.fsum(remap[k] for k in ("sand_transfer_residual","silt_transfer_residual","clay_transfer_residual")),
          solid=remap["post_solid_sediment_residual"]-summary["solid_sediment_residual"]-remap["solid_transfer_residual"])
        # An unexpected remap correction must be investigated, not silently absorbed into this audit.
        require(abs(identities["water"])<1e-12 and abs(identities["sediment"])<1e-7 and abs(identities["solid"])<1e-7,
                "scalar remap identity differs; inspect possible new correction before broadening")
        storage_identity=remap["post_water_storage"]-summary["water_storage"]-remap["water_transfer_residual"]
        require(abs(storage_identity)<=decimal12_bound(summary["water_storage"])+.00001,"remap storage identity differs")
        inputs=helper.normalization(p);water,sediment=inputs["prescribed_water_input_m3"],inputs["prescribed_sediment_input_kg"]
        normalized=dict(pre_water=summary["water_residual"]/water,pre_suspension_plus_deposition=summary["sediment_residual"]/sediment,
          pre_full_solid=summary["solid_sediment_residual"]/sediment,post_water=remap["post_water_residual"]/water,
          post_suspension_plus_deposition=remap["post_sediment_residual"]/sediment,post_full_solid=remap["post_solid_sediment_residual"]/sediment)
        end["raster_mineral_mass_minus_deposition_source_kg"]=end["event_deposit_mineral_mass_from_raster_kg"]-stored["deposited_mass_kg"]
        require(abs(end["raster_mineral_mass_minus_deposition_source_kg"])<=
                end["event_deposit_mineral_mass_storage_bound_kg"],"pre-remap mineral deposit/source mismatch exceeds float32 storage bound")
        cases[name]=dict(parameters=p,finished_utc=rec["utc_finished"],exit_code=rec["exit_code"],summary=summary,
          remap=remap,checkpoint=stored,checkpoint_bytes=len(blobs["checkpoint.bin"]),inventory_reaggregation=reaggregation,
          scalar_ledger_identity_errors=identities,water_storage_identity_error_m3=storage_identity,
          prescribed_inputs=inputs,signed_normalized_residuals=normalized,peak=peak,end=end,
          hashes={n:sha(blobs[n]) for n in ARTIFACTS})
    require(geometry["baseline250"]==geometry["fine125"],"common initial 250 m channel geometry differs")
    comparison={}
    for metric in ("alpha","interface_fraction","mean_water","beta","ridge_height","channel_depth","water_storage"):
        a,b=cases["baseline250"]["summary"][metric],cases["fine125"]["summary"][metric]
        comparison[metric]=dict(baseline250=a,fine125=b,difference=b-a,percent=100*(b/a-1) if a else None)
    a,b=cases["baseline250"]["checkpoint"]["deposited_mass_kg"],cases["fine125"]["checkpoint"]["deposited_mass_kg"]
    comparison["deposition_source_mineral_mass_kg"]=dict(baseline250=a,fine125=b,difference=b-a,percent=100*(b/a-1) if a else None)
    native={}
    for phase in ("peak","end"):
        native[phase]={}
        for metric in ("floodplain_area_m2","floodplain_water_volume_m3","inundated_area_m2",
                       "total_water_volume_from_raster_and_csv_m3","event_deposit_bulk_volume_m3",
                       "event_deposit_mineral_mass_from_raster_kg"):
            a,b=cases["baseline250"][phase][metric],cases["fine125"][phase][metric]
            native[phase][metric]=dict(baseline250=a,fine125=b,difference=b-a,percent=100*(b/a-1) if a else None)
    initial_difference={k:cases["fine125"]["inventory_reaggregation"][k]-cases["baseline250"]["inventory_reaggregation"][k]
                       for k in ("implied_initial_water_storage_m3","implied_initial_full_solid_inventory_kg")}
    return dict(cases=cases, parameter_differences=differences, metric_comparison=comparison,
        native_grid_integral_comparison=native, implied_initial_inventory_difference_between_grids=initial_difference,
        common_250m_footprint_fields={phase: compatible_fields(
            phase_arrays['baseline250'][phase], phase_arrays['fine125'][phase],
            phase_metadata['baseline250'][phase], phase_metadata['fine125'][phase], helper)
            for phase in ('peak', 'end')})


def verify(folder):
    """Verify retained identity and recompute native arrays without historical-path access."""
    folder = Path(folder)
    helper_file = folder / 'time-step.py'
    require(sha(helper_file.read_bytes()) == HELPER_SHA256, 'retained numeric helper hash differs')
    helper = SimpleNamespace(**runpy.run_path(str(helper_file)))
    capture_bytes = (folder / 'fine-grid-capture.json').read_bytes()
    capture = json.loads(capture_bytes.decode())
    require(capture['format'] == 1 and capture['stability_check']['unchanged_files'] == 30 and
            capture['stability_check']['minimum_pause_seconds'] >= 2,
            'unsupported capture format or missing stable terminal capture')
    archive_bytes = (folder / 'fine-grid-inputs.tar.xz').read_bytes()
    require(capture['archive']['file'] == 'fine-grid-inputs.tar.xz' and
            len(archive_bytes) == capture['archive']['bytes'] and
            sha(archive_bytes) == capture['archive']['sha256'], 'retained archive size or hash differs')
    identity = capture['source_identity']
    require(identity['corrected_binary_sha256'] == BINARY and identity['byte_order'] == 'little' and
            identity['pointer_and_size_t_bytes'] == 8 and identity['frozen_source_sha256'] == FROZEN_SOURCE_SHA256 and
            identity['validation_provenance_sha256'] == PROVENANCE_SHA256 and
            capture['helper_sha256'] == {'time-step.py': HELPER_SHA256} and
            set(identity['cases']) == set(CASES), 'incorrect captured source/layout/helper identity')
    expected = capture['archive']['member_sha256']
    artifacts = helper.ARTIFACTS + ('process_status.json',)
    required = {'validation/runs/' + name + '/' + f for name in CASES for f in artifacts} | set(EXTRA_SHA256)
    require(set(expected) == required and capture['archive']['members'] == len(required) and
            all(expected[k] == v for k, v in EXTRA_SHA256.items()),
            'capture member set or pinned terminal evidence differs')
    members = {}
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode='r:xz') as archive:
        for item in archive:
            require(item.isfile() and item.name in required and item.name not in members,
                    'unsafe, duplicate, or unexpected archive member')
            require((item.mode, item.uid, item.gid, item.uname, item.gname, item.mtime) ==
                    (0o644, 0, 0, '', '', 0), 'archive metadata is not normalized')
            blob = archive.extractfile(item).read()
            require(sha(blob) == expected[item.name], 'archive member hash differs: ' + item.name)
            members[item.name] = blob
    require(list(members) == sorted(required), 'retained archive is incomplete or not sorted')
    prior_capture = json.loads(members['evidence/time-step-capture.json'].decode())
    audited = json.loads(members['evidence/terminal.json'].decode())
    readiness = json.loads(members['evidence/readiness.json'].decode())
    manifest = json.loads(members['evidence/validation-manifest.json'].decode())
    provenance = json.loads(members['evidence/validation-provenance.json'].decode())
    require(provenance == manifest['provenance'] and provenance['binary_sha256'] == BINARY and
            provenance['source_sha256'] == FROZEN_SOURCE_SHA256 and
            audited['helper_sha256'] == HELPER_SHA256 and audited['binary_sha256'] == BINARY and
            audited['frozen_source_sha256'] == FROZEN_SOURCE_SHA256 and
            audited['original_pid_absent'] is True and audited['terminal_manifest_agrees'] is True and
            audited['readiness_sha256'] == EXTRA_SHA256['evidence/readiness.json'] and
            audited['observed_original_process'] == readiness['second'] and readiness['cpu_ticks_delta'] > 0,
            'retained terminal provenance differs')
    blobs_by_case, processes = {}, {}
    for name, dx in zip(CASES, (250., 125.)):
        prefix = 'validation/runs/' + name + '/'
        data = {f: members[prefix + f] for f in artifacts}
        process = json.loads(data['process_status.json'].decode())
        require(process['state'] == 'complete' and process['exit_code'] == 0 and
                process['binary_sha256'] == BINARY and process['name'] == name and
                [c for c in manifest['cases'] if c['name'] == name] == [process],
                'case lacks corrected completed process identity')
        require(set(process['artifact_sha256']) == set(helper.ARTIFACTS) and
                all(sha(data[f]) == process['artifact_sha256'][f] for f in helper.ARTIFACTS),
                'completed process artifact hashes differ')
        original = identity['cases'][name]
        require(original['process_pid'] == process['pid'] and original['process_pid_absent_at_capture'] is True and
                original['original_command'] == process['command'] and original['utc_started'] == process['utc_started'] and
                original['utc_finished'] == process['utc_finished'] and set(original['source_files']) == set(data) and
                all(original['source_files'][f]['sha256'] == sha(blob) and
                    original['source_files'][f]['bytes'] == len(blob) for f, blob in data.items()),
                'capture identity differs from retained terminal records')
        if name == 'baseline250':
            require(all(sha(data[f]) == prior_capture['archive']['member_sha256'][prefix + f] for f in artifacts),
                    'baseline bytes differ from prior retained capture')
        else:
            require(process == audited['terminal_process'] and
                    all(sha(data[f]) == audited['candidate_source_files'][f]['sha256'] for f in artifacts) and
                    process['command'] == readiness['second']['argv'],
                    'fine-grid bytes differ from completed terminal audit')
        command = process['command']
        require(len(command) % 2 == 1 and Path(command[0]).name == 'ridge-' + BINARY,
                'unexpected original executable command')
        options = dict(zip(command[1::2], command[2::2]))
        flags = {'--config', '--runs', '--run', '--floods', '--out'}
        if name == 'fine125':
            flags.add('--dx')
            require(options.get('--dx') == '125', 'incorrect fine-grid command')
        require(set(options) == flags and len(options) == len(command) // 2 and
                options['--floods'] == '1' and options['--run'] == '11' and Path(options['--out']).name == name,
                'unexpected original process command')
        require(data['parameters.txt'].decode().splitlines()[0] == 'command ' + ' '.join(command),
                'parameter command differs from terminal process record')
        p = parameters(data['parameters.txt'], helper)
        require(all(p[k] == v for k, v in dict(dx=dx, cfl=.4, floods=1, run=11, duration=1728000,
                length=72000, width=48000, A=0, C=.003, E=1, fine=0, concentration_scale=.001,
                tau_critical=.1).items()), 'unexpected first-flood scope')
        require(data['status.txt'] == b'complete 1 floods\n', 'case status is incomplete')
        blobs_by_case[name], processes[name] = data, process
    result = analyse(blobs_by_case, helper)
    require(all(value == audited[key] for key, value in result.items()),
            'portable numeric replay differs from retained terminal audit')
    for name in CASES:
        result['cases'][name]['process'] = processes[name]
    method = dict(audited['method'])
    method['day12'] = 'Both day12 and day20 native fields are replayed from retained original output bytes.'
    method['replay'] = ('Portable replay repeats the retained terminal auditor arithmetic from archived bytes. '
        'It reaggregates current checkpoint water, suspended classes, and bed-plus-suspension-plus-bank inventory; '
        'initial water/full-solid references remain inferred, not regenerated. Historical process observations '
        'are preserved evidence and are not re-observed; the model is not rerun.')
    result.update(format=1, status='verified', baseline_case='baseline250', scope=SCOPE,
        processor_sha256=sha(Path(__file__).read_bytes()), method=method,
        evidence=dict(captured_utc=capture['captured_utc'], capture_sha256=sha(capture_bytes),
            archive_sha256=sha(archive_bytes), member_sha256=expected,
            helper_sha256={'time-step.py': HELPER_SHA256}, binary_sha256=BINARY,
            original_source_identity=identity, retained_terminal_evidence_sha256=EXTRA_SHA256))
    return result


def main():
    require(len(sys.argv) <= 2, 'usage: fine-grid.py [retained-folder]')
    folder = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).resolve().parent
    result = verify(folder)
    require(json.loads((folder / 'fine-grid.json').read_text()) == result,
            'saved analysis differs from verified archive replay')
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
