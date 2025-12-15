"""
Boltz Web API - FastAPI wrapper for Boltz structure prediction.

This API provides REST endpoints to submit and retrieve structure predictions.
"""

import asyncio
import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

import numpy as np
import torch
import yaml
from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# API Configuration
API_VERSION = "1.0.0"
JOBS_DIR = Path(os.getenv("BOLTZ_API_JOBS_DIR", "./api_jobs"))
MAX_JOB_AGE_HOURS = int(os.getenv("BOLTZ_API_MAX_JOB_AGE_HOURS", "72"))

# Create jobs directory
JOBS_DIR.mkdir(exist_ok=True, parents=True)

# In-memory job storage (use Redis/database for production)
jobs_db: Dict[str, Dict] = {}

# Cache for ligand predictions (SMILES -> list of job_ids)
# This allows reusing predictions for the same ligand
prediction_cache: Dict[str, List[str]] = {}

# ==================== Protein Target Configurations ====================

# GLP1R (Glucagon-like peptide-1 receptor)
GLP1R_SEQUENCE = "MAGAPGLLRLALLLLGMVGRAGPRPQGATVSLWETVQKWREYRRQCQRSLTEDPPPATDLFCNRTFDEYACWPDGEPGSFVNVSCPWYLPWASSVPQGHVYRFCTAEGLWLQKDNSSLPWRDLSECEESKRGERSSPEEQLLFLYIIYTVGYALSFSALVIASAILLGFRHLHCTRNYIHLNLFASFILRALSVFIKDAALKWMYSTAAQQHQWDGLLSYQDSLSCRLVFLLMQYCVAANYYWLLVEGVYLYTLLAFSVLSEQWIFRLYVSIGWGVPLLFVVPWGIVKYLYEDEGCWTRNSNMNYWLIIRLPILFAIGVNFLIFVRVICIVVSKLKANLMCKTDIKCRLAKSTLTLIPLLGTHEVIFAFVMDEHARGTLRFIKLFTELSFTSFQGLMVAILYCFVNNEVQLEFRKSWERWRLEHLHIQRDSSMKPLKCPTSSLSSGATAGSSMYTATCQASCS"
GLP1R_ECD_RANGES = list(range(24, 140)) + list(range(202, 228)) + list(range(291, 306)) + list(range(371, 384))
GLP1R_TM_RANGES = list(range(140, 161)) + list(range(176, 202)) + list(range(228, 252)) + list(range(266, 291)) + list(range(306, 329)) + list(range(349, 371)) + list(range(384, 405))
GLP1R_BINDING_POCKET = GLP1R_ECD_RANGES + GLP1R_TM_RANGES

# GIPR (Glucose-dependent insulinotropic polypeptide receptor)
GIPR_SEQUENCE = "MTTSPILQLLLRLSLCGLLLQRAETGSKGQTAGELYQRWERYRRECQETLAAAEPPSGLACNGSFDMYVCWDYAAPNATARASCPWYLPWHHHVAAGFVLRQCGSDGQWGLWRDHTQCENPEKNEAFLDQRLILERLQVMYTVGYSLSLATLLLALLILSLFRRLHCTRNYIHINLFTSFMLRAAAILSRDRLLPRPGPYLGDQALALWNQALAACRTAQIVTQYCVGANYTWLLVEGVYLHSLLVLVGGSEEGHFRYYLLLGWGAPALFVIPWVIVRYLYENTQCWERNEVKAIWWIIRTPILMTILINFLIFIRILGILLSKLRTRQMRCRDYRLRLARSTLTLVPLLGVHEVVFAPVTEEQARGALRFAKLGFEIFLSSFQGFLVSVLYCFINKEVQSEIRRGWHHCRLRRSLGEEQRQLPERAFRALPSGSGPGEVPTSRGLSSGTLPGPGNEASRELESYC"
GIPR_ECD_RANGES = list(range(22, 139)) + list(range(190, 218)) + list(range(279, 294)) + list(range(363, 378))
GIPR_TM_RANGES = list(range(139, 162)) + list(range(170, 190)) + list(range(218, 243)) + list(range(255, 279)) + list(range(294, 320)) + list(range(342, 363)) + list(range(379, 399))
GIPR_BINDING_POCKET = GIPR_ECD_RANGES + GIPR_TM_RANGES

# GCGR (Glucagon receptor)
GCGR_SEQUENCE = "MPPCQPQRPLLLLLLLLACQPQVPSAQVMDFLFEKWKLYGDQCHHNLSLLPPPTELVCNRTFDKYSCWPDTPANTTANISCPWYLPWHHKVQHRFVFKRCGPDGQWVRGPRGQPWRDASQCQMDGEEIEVQKEVAKMYSSFQVMYTVGYSLSLGALLLALAILGGLSKLHCTRNAIHANLFASFVLKASSVLVIDGLLRTRYSQKIGDDLSVSTWLSDGAVAGCRVAAVFMQYGIVANYCWLLVEGLYLHNLLGLATLPERSFFSLYLGIGWGAPMLFVVPWAVVKCLFENVQCWTSNDNMGFWWILRFPVFLAILINFFIFVRIVQLLVAKLRARQMHHTDYKFRLAKSTLTLIPLLGVHEVVFAFVTDEHAQGTLRSAKLFFDLFLSSFQGLLVAVLYCFLNKEVQSELRRRWHRWRLGKVLWEERNTSNHRASSSPGHGPPSKELQFGRGGGSQDSSAETPLAGGLPRLAESPF"
GCGR_ECD_RANGES = list(range(26, 137)) + list(range(199, 226)) + list(range(286, 305)) + list(range(370, 382))
GCGR_TM_RANGES = list(range(137, 162)) + list(range(174, 199)) + list(range(226, 250)) + list(range(264, 286)) + list(range(304, 327)) + list(range(351, 370)) + list(range(382, 403))
GCGR_BINDING_POCKET = GCGR_ECD_RANGES + GCGR_TM_RANGES

# Protein target configurations
PROTEIN_TARGETS = {
    "GLP1R": {
        "sequence": GLP1R_SEQUENCE,
        "binding_pocket": GLP1R_BINDING_POCKET,
        "name": "GLP-1 Receptor"
    },
    "GIPR": {
        "sequence": GIPR_SEQUENCE,
        "binding_pocket": GIPR_BINDING_POCKET,
        "name": "GIP Receptor"
    },
    "GCGR": {
        "sequence": GCGR_SEQUENCE,
        "binding_pocket": GCGR_BINDING_POCKET,
        "name": "Glucagon Receptor"
    }
}


# ==================== Helper Functions ====================


def detect_accelerator(min_free_memory_gb: float = 8.0) -> tuple[str, int]:
    """Detect the best available accelerator.
    
    Args:
        min_free_memory_gb: Minimum free GPU memory in GB required to use GPU
    
    Note: For Mac with MPS, we return 'cpu' because Boltz CLI doesn't accept 'mps',
    but PyTorch will automatically use MPS when available.
    """
    if torch.cuda.is_available():
        # Check available GPU memory
        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.free', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, check=True
            )
            free_memory_mb = int(result.stdout.strip().split('\n')[0])
            free_memory_gb = free_memory_mb / 1024
            
            if free_memory_gb >= min_free_memory_gb:
                return "gpu", torch.cuda.device_count()
            else:
                print(f"GPU has only {free_memory_gb:.1f}GB free (need {min_free_memory_gb}GB), using CPU")
                return "cpu", 1
        except Exception as e:
            print(f"Could not check GPU memory: {e}, defaulting to GPU")
            return "gpu", torch.cuda.device_count()
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        # Use 'cpu' for Boltz CLI, but MPS will be used automatically by PyTorch
        return "cpu", 1
    else:
        return "cpu", 1


# ==================== Lifespan Events ====================


def restore_jobs_from_disk():
    """Restore job metadata from existing job directories on disk."""
    try:
        if not JOBS_DIR.exists():
            print(f"Jobs directory does not exist: {JOBS_DIR}")
            return
        
        print(f"Scanning for existing jobs in {JOBS_DIR}...")
        restored_count = 0
        for job_dir in JOBS_DIR.iterdir():
            if not job_dir.is_dir() or not job_dir.name.startswith("job_"):
                continue
            
            job_id = job_dir.name
            if job_id in jobs_db:
                continue  # Already in memory
            
            # Check if job has output
            output_dir = job_dir / "output"
            if not output_dir.exists():
                continue
            
            # Scan for prediction files
            predictions = []
            confidence_files = []
            affinity_files = []
            
            for result_dir in output_dir.glob("boltz_results_*"):
                pred_dir = result_dir / "predictions"
                if pred_dir.exists():
                    for file in pred_dir.rglob("*_model_*.cif"):
                        predictions.append(str(file.relative_to(job_dir)))
                    for file in pred_dir.rglob("confidence_*_model_*.json"):
                        confidence_files.append(str(file.relative_to(job_dir)))
                    for file in pred_dir.rglob("affinity_*.json"):
                        affinity_files.append(str(file.relative_to(job_dir)))
            
            # Extract metrics from result files
            metrics = extract_metrics_from_files(confidence_files, affinity_files, job_dir)
            
            # Get timestamps from directory
            created_at = datetime.fromtimestamp(job_dir.stat().st_ctime).isoformat()
            modified_at = datetime.fromtimestamp(job_dir.stat().st_mtime).isoformat()
            
            # Try to extract job_name from input.yaml or use job_id as fallback
            job_name = None
            yaml_path = job_dir / "input.yaml"
            if yaml_path.exists():
                try:
                    with open(yaml_path, 'r') as f:
                        input_data = yaml.safe_load(f)
                        # Try to infer job name from protein sequence or use job_id
                        for seq in input_data.get('sequences', []):
                            if 'protein' in seq:
                                # Use first few chars of protein ID if available
                                protein_id = seq['protein'].get('id', '')
                                if protein_id:
                                    job_name = f"{protein_id}-{job_id.split('_')[1][:8]}"
                                    break
                except:
                    pass
            
            if not job_name:
                job_name = job_id  # Fallback to job_id
            
            # Restore job metadata
            jobs_db[job_id] = {
                "status": "completed" if predictions else "unknown",
                "created_at": created_at,
                "started_at": created_at,
                "completed_at": modified_at,
                "predictions": predictions,
                "confidence_files": confidence_files,
                "affinity_files": affinity_files,
                "metrics": metrics,  # Store extracted metrics
                "error": None,
                "stdout": "",
                "job_name": job_name,  # Add job_name field
            }
            restored_count += 1
        
        if restored_count > 0:
            print(f"✓ Restored {restored_count} jobs from disk")
            
            # Rebuild prediction cache from restored jobs
            # Group jobs by ligand SMILES (read from input.yaml)
            smiles_to_jobs = {}
            for job_id in jobs_db:
                job_dir = JOBS_DIR / job_id
                yaml_path = job_dir / "input.yaml"
                if yaml_path.exists():
                    try:
                        with open(yaml_path, 'r') as f:
                            input_data = yaml.safe_load(f)
                            # Extract SMILES from ligand sequence
                            for seq in input_data.get('sequences', []):
                                if 'ligand' in seq:
                                    smiles = seq['ligand'].get('smiles')
                                    if smiles:
                                        if smiles not in smiles_to_jobs:
                                            smiles_to_jobs[smiles] = []
                                        smiles_to_jobs[smiles].append(job_id)
                                        break
                    except Exception as e:
                        print(f"Warning: Could not read input.yaml for {job_id}: {e}")
            
            # Populate cache for ligands with 3 completed jobs
            cache_count = 0
            for smiles, job_list in smiles_to_jobs.items():
                if len(job_list) == 3:
                    # Verify all jobs are completed
                    if all(jobs_db[jid]["status"] == "completed" for jid in job_list):
                        add_to_prediction_cache(smiles, job_list)
                        cache_count += 1
            
            if cache_count > 0:
                print(f"✓ Rebuilt cache with {cache_count} ligands")
        else:
            print("No existing jobs found to restore")
    except Exception as e:
        print(f"Error restoring jobs: {e}")
        import traceback
        traceback.print_exc()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    accelerator, device_count = detect_accelerator()
    
    # Determine actual hardware
    if torch.cuda.is_available():
        hw_info = f"CUDA GPU ({torch.cuda.device_count()} devices)"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        hw_info = "Apple MPS (Metal Performance Shaders)"
    else:
        hw_info = "CPU only"
    
    print(f"Boltz API v{API_VERSION} starting...")
    print(f"Jobs directory: {JOBS_DIR.absolute()}")
    print(f"Max job age: {MAX_JOB_AGE_HOURS} hours")
    print(f"Hardware: {hw_info}")
    print(f"Boltz accelerator setting: {accelerator}")
    
    # Restore existing jobs from disk
    restore_jobs_from_disk()
    
    print("API ready!")
    
    yield
    
    # Shutdown
    print("Shutting down Boltz API...")


# Initialize FastAPI app
app = FastAPI(
    title="Boltz Structure Prediction API",
    description="REST API for biomolecular structure and affinity prediction using Boltz",
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Pydantic Models ====================


class ProteinSequence(BaseModel):
    """Protein sequence definition."""

    id: str | List[str] = Field(..., description="Chain ID(s)")
    sequence: str = Field(..., description="Amino acid sequence")
    msa: Optional[str] = Field(None, description="Path to MSA file or 'empty'")


class LigandSequence(BaseModel):
    """Ligand definition."""

    id: str | List[str] = Field(..., description="Chain ID(s)")
    smiles: Optional[str] = Field(None, description="SMILES string")
    ccd: Optional[str] = Field(None, description="CCD code")


class DNASequence(BaseModel):
    """DNA sequence definition."""

    id: str | List[str] = Field(..., description="Chain ID(s)")
    sequence: str = Field(..., description="DNA sequence")


class RNASequence(BaseModel):
    """RNA sequence definition."""

    id: str | List[str] = Field(..., description="Chain ID(s)")
    sequence: str = Field(..., description="RNA sequence")


class AffinityProperty(BaseModel):
    """Affinity prediction property."""

    binder: str = Field(..., description="Chain ID of the binder molecule")


class PredictionRequest(BaseModel):
    """Structure prediction request."""

    sequences: List[Dict] = Field(..., description="List of sequences/molecules")
    properties: Optional[List[Dict]] = Field(
        None, description="Properties to predict (e.g., affinity)"
    )
    use_msa_server: bool = Field(True, description="Auto-generate MSA")
    use_potentials: bool = Field(False, description="Use inference-time potentials")
    recycling_steps: int = Field(3, ge=1, le=20, description="Number of recycling steps")
    sampling_steps: int = Field(200, ge=50, le=500, description="Diffusion sampling steps")
    diffusion_samples: int = Field(1, ge=1, le=50, description="Number of samples")
    output_format: str = Field("mmcif", description="Output format (pdb or mmcif)")
    devices: Optional[int] = Field(None, description="Number of devices (auto-detected if None)")
    accelerator: Optional[str] = Field(None, description="Accelerator type (auto-detected if None: gpu/mps/cpu)")


class JobStatus(BaseModel):
    """Job status response."""

    job_id: str
    status: str  # pending, running, completed, failed
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: Optional[str] = None
    error: Optional[str] = None


class JobResult(BaseModel):
    """Job result response."""

    job_id: str
    status: str
    predictions: Optional[List[str]] = None
    confidence_scores: Optional[Dict] = None
    affinity_scores: Optional[Dict] = None
    output_files: Optional[List[str]] = None


class ProteinLigandBindingRequest(BaseModel):
    """Protein-ligand binding prediction request."""
    
    ligand_smiles: str = Field(..., description="SMILES string of the ligand")
    template_path: Optional[str] = Field(None, description="Path to template CIF file (optional)")
    use_msa_server: bool = Field(True, description="Auto-generate MSA")
    recycling_steps: int = Field(3, ge=1, le=20, description="Number of recycling steps")
    sampling_steps: int = Field(200, ge=50, le=500, description="Diffusion sampling steps")
    diffusion_samples: int = Field(1, ge=1, le=50, description="Number of samples")


class ProteinLigandBindingResult(BaseModel):
    """Protein-ligand binding prediction result."""
    
    job_ids: List[str] = Field(..., description="Job IDs for the three predictions")
    ligand_smiles: str = Field(..., description="SMILES string of the ligand")
    status: str = Field(..., description="Overall status")
    message: str = Field(..., description="Status message")


# ==================== Helper Functions ====================


def generate_job_id() -> str:
    """Generate unique job ID."""
    return f"job_{uuid.uuid4().hex[:12]}_{int(datetime.now().timestamp())}"


def get_job_dir(job_id: str) -> Path:
    """Get job directory path."""
    return JOBS_DIR / job_id


def generate_cache_key(ligand_smiles: str) -> str:
    """
    Generate a cache key for a ligand SMILES string.
    Normalizes the SMILES to ensure consistent caching.
    """
    import hashlib
    # Use hash to handle long SMILES and ensure consistency
    return hashlib.md5(ligand_smiles.encode()).hexdigest()


def check_prediction_cache(ligand_smiles: str) -> Optional[List[str]]:
    """
    Check if predictions exist for this ligand in the cache.
    
    Returns:
        List of job_ids if found, None otherwise
    """
    cache_key = generate_cache_key(ligand_smiles)
    
    if cache_key in prediction_cache:
        job_ids = prediction_cache[cache_key]
        
        # Verify all jobs still exist and are completed
        valid_jobs = []
        for job_id in job_ids:
            if job_id in jobs_db and jobs_db[job_id]["status"] == "completed":
                valid_jobs.append(job_id)
        
        if len(valid_jobs) == 3:  # We expect 3 replicates
            return valid_jobs
        else:
            # Cache is stale, remove it
            del prediction_cache[cache_key]
    
    return None


def add_to_prediction_cache(ligand_smiles: str, job_ids: List[str]):
    """
    Add completed predictions to the cache.
    """
    cache_key = generate_cache_key(ligand_smiles)
    prediction_cache[cache_key] = job_ids


def create_yaml_input(job_dir: Path, request: PredictionRequest) -> Path:
    """Create YAML input file from request."""
    yaml_data = {
        "version": 1,
        "sequences": request.sequences,
    }
    
    if request.properties:
        yaml_data["properties"] = request.properties
    
    yaml_path = job_dir / "input.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f, default_flow_style=False)
    
    return yaml_path


def extract_metrics_from_files(confidence_files: List[str], affinity_files: List[str], job_dir: Path) -> Dict:
    """
    Extract key metrics from BOLTZ result files.
    Based on the notebook's extract_metrics function.
    """
    metrics = {}
    
    # Extract confidence metrics
    for conf_file in confidence_files:
        try:
            with open(job_dir / conf_file) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    metrics.update({
                        "confidence_score": data.get("confidence_score", 0),
                        "ptm": data.get("ptm", 0),
                        "iptm": data.get("iptm", 0),
                        "plddt": data.get("complex_plddt", 0)
                    })
                    break  # Use first confidence file
        except Exception as e:
            print(f"Warning: Could not read confidence file {conf_file}: {e}")
    
    # Extract affinity metrics
    for aff_file in affinity_files:
        try:
            with open(job_dir / aff_file) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # Raw BOLTZ output: log10(IC50 in μM)
                    log_ic50_uM = data.get("affinity_pred_value", 0)
                    
                    # Convert log10(IC50 in μM) to IC50 in μM
                    ic50_uM = 10 ** log_ic50_uM
                    
                    # Convert to nM (1 μM = 1000 nM)
                    ic50_nM = ic50_uM * 1000
                    
                    # Convert to M for proper pIC50 calculation
                    ic50_M = ic50_uM * 1e-6
                    
                    # Calculate standard pIC50 (negative log of IC50 in molar units)
                    pic50 = -np.log10(ic50_M) if ic50_M > 0 else 0
                    
                    # Calculate binding free energy in kcal/mol
                    delta_g_kcal = (6 - log_ic50_uM) * 1.364
                    
                    # Approximate Kd from IC50 (Kd ≈ IC50/2 for competitive inhibitors)
                    kd_uM = ic50_uM / 2
                    kd_nM = kd_uM * 1000
                    kd_M = kd_uM * 1e-6
                    
                    # Calculate pKd from Kd in molar units
                    pkd = -np.log10(kd_M) if kd_M > 0 else 0
                    
                    metrics.update({
                        # Raw BOLTZ output
                        "boltz_affinity_value": log_ic50_uM,
                        
                        # IC50 values
                        "ic50_uM": float(ic50_uM),
                        "ic50_nM": float(ic50_nM),
                        "pic50": float(pic50),
                        
                        # Kd approximations
                        "kd_uM": float(kd_uM),
                        "kd_nM": float(kd_nM),
                        "pkd": float(pkd),
                        
                        # Energy
                        "delta_g_kcal": float(delta_g_kcal),
                        
                        # Binding probability
                        "affinity_prob": data.get("affinity_probability_binary", 0)
                    })
                    break  # Use first affinity file
        except Exception as e:
            print(f"Warning: Could not read affinity file {aff_file}: {e}")
    
    return metrics


async def run_boltz_prediction(job_id: str, request: PredictionRequest) -> None:
    """Run Boltz prediction in background."""
    job_dir = get_job_dir(job_id)
    
    try:
        # Update job status
        jobs_db[job_id]["status"] = "running"
        jobs_db[job_id]["started_at"] = datetime.now().isoformat()
        
        # Auto-detect accelerator if not specified
        accelerator = request.accelerator
        devices = request.devices
        if accelerator is None or devices is None:
            detected_accelerator, detected_devices = detect_accelerator()
            if accelerator is None:
                accelerator = detected_accelerator
            if devices is None:
                devices = detected_devices
        
        # Check if input YAML already exists (e.g., created by protein-ligand-binding-sync with template)
        yaml_path = job_dir / "input.yaml"
        if not yaml_path.exists():
            # Create input YAML if it doesn't exist
            yaml_path = create_yaml_input(job_dir, request)
        
        # Build Boltz command
        cmd = [
            "boltz",
            "predict",
            str(yaml_path),
            "--out_dir",
            str(job_dir / "output"),
            "--cache",
            "/root/.boltz",  # Explicitly set cache directory
        ]
        
        if request.use_msa_server:
            cmd.append("--use_msa_server")
        
        if request.use_potentials:
            cmd.append("--use_potentials")
        
        cmd.extend([
            "--recycling_steps", str(request.recycling_steps),
            "--sampling_steps", str(request.sampling_steps),
            "--diffusion_samples", str(request.diffusion_samples),
            "--output_format", request.output_format,
            "--devices", str(devices),
            "--accelerator", accelerator,
        ])
        
        # Run prediction
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ.copy(),  # Pass environment variables
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            # Parse results - Boltz creates output in boltz_results_<name>/predictions/
            # Find the actual predictions directory
            boltz_results_dir = job_dir / "output"
            predictions = []
            confidence_files = []
            affinity_files = []
            
            # Search for prediction files in boltz_results_* directories
            for result_dir in boltz_results_dir.glob("boltz_results_*"):
                pred_dir = result_dir / "predictions"
                if pred_dir.exists():
                    # Boltz creates files in predictions/<input_name>/ subdirectories
                    # Search recursively for prediction files
                    # Note: BOLTZ creates .cif files even when output_format is mmcif
                    for file in pred_dir.rglob("*_model_*.cif"):
                        predictions.append(str(file.relative_to(job_dir)))
                    
                    # Find confidence files
                    for file in pred_dir.rglob("confidence_*_model_*.json"):
                        confidence_files.append(str(file.relative_to(job_dir)))
                    
                    # Find affinity files
                    for file in pred_dir.rglob("affinity_*.json"):
                        affinity_files.append(str(file.relative_to(job_dir)))
            
            # Extract metrics from result files
            metrics = extract_metrics_from_files(confidence_files, affinity_files, job_dir)
            
            # Update job with results
            jobs_db[job_id]["status"] = "completed"
            jobs_db[job_id]["completed_at"] = datetime.now().isoformat()
            jobs_db[job_id]["predictions"] = predictions
            jobs_db[job_id]["confidence_files"] = confidence_files
            jobs_db[job_id]["affinity_files"] = affinity_files
            jobs_db[job_id]["metrics"] = metrics  # Store extracted metrics
            jobs_db[job_id]["stdout"] = stdout.decode()
            
        else:
            # Prediction failed
            jobs_db[job_id]["status"] = "failed"
            jobs_db[job_id]["completed_at"] = datetime.now().isoformat()
            error_msg = stderr.decode() if stderr else "Unknown error"
            jobs_db[job_id]["error"] = error_msg
            jobs_db[job_id]["stdout"] = stdout.decode() if stdout else ""
            print(f"Job {job_id} failed with error: {error_msg}")
    
    except Exception as e:
        jobs_db[job_id]["status"] = "failed"
        jobs_db[job_id]["completed_at"] = datetime.now().isoformat()
        jobs_db[job_id]["error"] = f"{type(e).__name__}: {str(e)}"
        print(f"Job {job_id} exception: {e}")
        import traceback
        traceback.print_exc()


def cleanup_old_jobs() -> None:
    """Clean up old job directories."""
    from datetime import timedelta
    
    cutoff_time = datetime.now() - timedelta(hours=MAX_JOB_AGE_HOURS)
    
    for job_id, job_data in list(jobs_db.items()):
        created_at = datetime.fromisoformat(job_data["created_at"])
        if created_at < cutoff_time and job_data["status"] in ["completed", "failed"]:
            job_dir = get_job_dir(job_id)
            if job_dir.exists():
                shutil.rmtree(job_dir)
            del jobs_db[job_id]


# ==================== API Endpoints ====================


@app.get("/", tags=["General"])
async def root():
    """API root endpoint."""
    return {
        "name": "Boltz Structure Prediction API",
        "version": API_VERSION,
        "status": "running",
        "documentation": "/docs",
    }


@app.get("/health", tags=["General"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "jobs_count": len(jobs_db),
        "cached_ligands": len(prediction_cache),
    }


@app.get("/cache/status", tags=["General"])
async def cache_status():
    """Get cache status and statistics."""
    cache_info = []
    for cache_key, job_ids in prediction_cache.items():
        # Get ligand info from first job
        if job_ids and job_ids[0] in jobs_db:
            job_dir = JOBS_DIR / job_ids[0]
            yaml_path = job_dir / "input.yaml"
            ligand_smiles = None
            job_name = jobs_db[job_ids[0]].get("job_name", "unknown")
            
            if yaml_path.exists():
                try:
                    with open(yaml_path, 'r') as f:
                        input_data = yaml.safe_load(f)
                        for seq in input_data.get('sequences', []):
                            if 'ligand' in seq:
                                ligand_smiles = seq['ligand'].get('smiles', '')[:50] + '...'
                                break
                except:
                    pass
            
            cache_info.append({
                "cache_key": cache_key,
                "job_name": job_name,
                "ligand_smiles_preview": ligand_smiles,
                "job_ids": job_ids,
                "job_count": len(job_ids)
            })
    
    return {
        "total_cached_ligands": len(prediction_cache),
        "total_cached_jobs": sum(len(jobs) for jobs in prediction_cache.values()),
        "cached_ligands": cache_info
    }


@app.get("/jobs/{job_id}/status", response_model=JobStatus, tags=["Jobs"])
async def get_job_status(job_id: str):
    """
    Get the status of a prediction job.
    """
    if job_id not in jobs_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    
    job_data = jobs_db[job_id]
    
    return JobStatus(
        job_id=job_id,
        status=job_data["status"],
        created_at=job_data["created_at"],
        started_at=job_data.get("started_at"),
        completed_at=job_data.get("completed_at"),
        error=job_data.get("error"),
    )


@app.get("/jobs/{job_id}/download/{file_path:path}", tags=["Jobs"])
async def download_file(job_id: str, file_path: str):
    """
    Download a specific output file from a job.
    """
    if job_id not in jobs_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    
    file_full_path = get_job_dir(job_id) / file_path
    
    if not file_full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_path} not found",
        )
    
    # Security check: ensure file is within job directory
    if not str(file_full_path.resolve()).startswith(str(get_job_dir(job_id).resolve())):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    return FileResponse(
        path=file_full_path,
        filename=file_full_path.name,
        media_type="application/octet-stream",
    )


@app.get("/jobs", tags=["Jobs"])
async def list_jobs(
    status_filter: Optional[str] = None,
    limit: int = 100,
):
    """
    List all jobs, optionally filtered by status.
    """
    jobs = list(jobs_db.values())
    
    if status_filter:
        jobs = [j for j in jobs if j["status"] == status_filter]
    
    jobs = sorted(jobs, key=lambda x: x["created_at"], reverse=True)
    
    return {
        "total": len(jobs),
        "jobs": jobs[:limit],
    }


@app.delete("/jobs/{job_id}", tags=["Jobs"])
async def delete_job(job_id: str):
    """
    Delete a job and its associated files.
    """
    if job_id not in jobs_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    
    # Remove job directory
    job_dir = get_job_dir(job_id)
    if job_dir.exists():
        shutil.rmtree(job_dir)
    
    # Remove from database
    del jobs_db[job_id]
    
    return {"message": f"Job {job_id} deleted successfully"}


@app.get("/jobs/{job_id}/download/{file_path:path}", tags=["Jobs"])
async def download_job_file(job_id: str, file_path: str):
    """
    Download a specific file from a job's output directory.
    
    The file_path should be relative to the job directory (e.g., 
    'output/boltz_results_input/predictions/input/input_model_0.cif').
    
    This endpoint serves files with appropriate MIME types for direct download
    or viewing in the browser.
    """
    from fastapi.responses import FileResponse
    import mimetypes
    
    if job_id not in jobs_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    # Construct full file path
    job_dir = get_job_dir(job_id)
    full_path = job_dir / file_path
    
    # Security check: ensure the file is within the job directory
    try:
        full_path = full_path.resolve()
        job_dir = job_dir.resolve()
        if not str(full_path).startswith(str(job_dir)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: path traversal detected"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file path: {str(e)}"
        )
    
    # Check if file exists
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_path}"
        )
    
    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(str(full_path))
    if mime_type is None:
        # Default MIME types for common structure files
        if full_path.suffix.lower() in ['.cif', '.mmcif']:
            mime_type = 'chemical/x-cif'
        elif full_path.suffix.lower() == '.pdb':
            mime_type = 'chemical/x-pdb'
        elif full_path.suffix.lower() == '.json':
            mime_type = 'application/json'
        else:
            mime_type = 'application/octet-stream'
    
    # Return file
    return FileResponse(
        path=str(full_path),
        media_type=mime_type,
        filename=full_path.name
    )


@app.post("/protein-ligand-binding-sync", tags=["Protein-Ligand"])
async def predict_protein_ligand_binding_sync(
    request: ProteinLigandBindingRequest,
):
    """
    Predict protein-ligand binding for ALL THREE receptors (GLP1R, GIPR, GCGR) and return complete results (synchronous).
    
    This endpoint runs 3 predictions total (1 per receptor) and waits for all to complete before returning.
    With GPU acceleration, this typically takes 6-9 minutes for all three predictions.
    
    For the input SMILES (ligand), it predicts binding to:
    - GLP1R (Glucagon-like peptide-1 receptor)
    - GIPR (Glucose-dependent insulinotropic polypeptide receptor)
    - GCGR (Glucagon receptor)
    
    Returns complete metrics including:
    - boltz_affinity_value, affinity_prob
    - ic50_nM, ic50_uM, pic50
    - kd_nM, kd_uM, pkd
    - delta_g_kcal
    - confidence_score, ptm, iptm, plddt
    - Structure files (CIF)
    
    The response includes individual results for each receptor.
    """
    # Receptor-specific template paths (relative to api directory)
    TEMPLATE_BASE_PATH = "/app/template_path"
    RECEPTOR_TEMPLATES = {
        "GLP1R": f"{TEMPLATE_BASE_PATH}/GLP.cif",
        "GIPR": f"{TEMPLATE_BASE_PATH}/GIP.cif",
        "GCGR": f"{TEMPLATE_BASE_PATH}/GCGR.cif"
    }
    
    # Hardcoded prediction parameters (simplified API)
    use_msa_server = True
    recycling_steps = 3
    sampling_steps = 200
    diffusion_samples = 1
    
    # Check cache first
    cached_job_ids = check_prediction_cache(request.ligand_smiles)
    
    if cached_job_ids:
        # Cache hit! Return cached results
        print(f"✓ Cache hit for ligand SMILES: {request.ligand_smiles[:50]}...")
        job_ids = cached_job_ids
    else:
        # Cache miss - run new predictions for ALL THREE receptors
        print(f"Cache miss for ligand SMILES: {request.ligand_smiles[:50]}... Running predictions for GLP1R, GIPR, GCGR...")
        
        job_ids = []
        
        # Define receptor configurations (one prediction per receptor)
        receptors = [
            {
                "name": "GLP1R",
                "sequence": GLP1R_SEQUENCE,
                "binding_pocket": GLP1R_BINDING_POCKET,
            },
            {
                "name": "GIPR",
                "sequence": GIPR_SEQUENCE,
                "binding_pocket": GIPR_BINDING_POCKET,
            },
            {
                "name": "GCGR",
                "sequence": GCGR_SEQUENCE,
                "binding_pocket": GCGR_BINDING_POCKET,
            }
        ]
        
        # Run one prediction per receptor
        for receptor in receptors:
            print(f"Running prediction for {receptor['name']}...")
            
            # Generate job name for this receptor
            job_name = f"{receptor['name']}-LIGAND"
            
            # Single prediction per receptor (not multiple replicates)
            if True:  # Keep indentation consistent
                # Generate job ID
                job_id = generate_job_id()
                job_dir = get_job_dir(job_id)
                job_dir.mkdir(parents=True, exist_ok=True)
                
                # Prepare contacts for binding pocket
                contacts = [["A", i] for i in receptor["binding_pocket"]]
                
                # Build input data
                input_data = {
                    "version": 1,
                    "sequences": [
                        {
                            "protein": {
                                "id": "A",
                                "sequence": receptor["sequence"]
                            }
                        },
                        {
                            "ligand": {
                                "id": "C",
                                "smiles": request.ligand_smiles
                            }
                        }
                    ],
                    "constraints": [
                        {
                            "pocket": {
                                "binder": "C",
                                "contacts": contacts
                            }
                        }
                    ],
                    "properties": [
                        {
                            "affinity": {
                                "binder": "C",
                                "target": "A"
                            }
                        }
                    ]
                }
                
                # Add receptor-specific template
                receptor_template = RECEPTOR_TEMPLATES.get(receptor["name"])
                if receptor_template:
                    input_data["template"] = {
                        "complex_cif": receptor_template
                    }
                    print(f"Using template: {receptor_template} for {receptor['name']}")
                
                # Create PredictionRequest with hardcoded parameters
                pred_request = PredictionRequest(
                    sequences=input_data["sequences"],
                    properties=input_data.get("properties"),
                    use_msa_server=use_msa_server,
                    recycling_steps=recycling_steps,
                    sampling_steps=sampling_steps,
                    diffusion_samples=diffusion_samples,
                    output_format="mmcif",
                )
                
                # Store job metadata
                jobs_db[job_id] = {
                    "status": "pending",
                    "created_at": datetime.now().isoformat(),
                    "started_at": None,
                    "completed_at": None,
                    "predictions": [],
                    "confidence_files": [],
                    "affinity_files": [],
                    "error": None,
                    "job_name": job_name,
                    "receptor": receptor["name"],  # Track which receptor this is for
                }
                
                # Save input YAML with constraints
                yaml_path = job_dir / "input.yaml"
                with open(yaml_path, "w") as f:
                    yaml.dump(input_data, f, default_flow_style=False)
                
                # Run prediction synchronously (wait for completion)
                await run_boltz_prediction(job_id, pred_request)
                
                job_ids.append(job_id)
        
        # Add to cache after all predictions complete
        add_to_prediction_cache(request.ligand_smiles, job_ids)
    
    # Collect results grouped by receptor
    results_by_receptor = {"GLP1R": [], "GIPR": [], "GCGR": []}
    
    for job_id in job_ids:
        job_data = jobs_db[job_id]
        receptor_name = job_data.get("receptor", "GLP1R")  # Default to GLP1R for backward compatibility
        
        if job_data["status"] == "completed":
            metrics = job_data.get("metrics", {})
            
            # Build result for this job
            result = {
                "job_id": job_id,
                "job_name": job_data.get("job_name"),
                "receptor": receptor_name,
                "status": "completed",
                "confidence_scores": {
                    k: v for k, v in metrics.items() 
                    if k in ["confidence_score", "ptm", "iptm", "plddt", "complex_plddt", "complex_pde"]
                },
                "affinity_scores": {
                    k: v for k, v in metrics.items() 
                    if k in ["boltz_affinity_value", "affinity_prob", "ic50_nM", "ic50_uM", 
                             "pic50", "delta_g_kcal", "kd_nM", "kd_uM", "pkd", "binding_classification"]
                },
                "structure_files": job_data.get("predictions", [])
            }
        else:
            # Job failed
            result = {
                "job_id": job_id,
                "job_name": job_data.get("job_name"),
                "receptor": receptor_name,
                "status": job_data["status"],
                "error": job_data.get("error")
            }
        
        if receptor_name in results_by_receptor:
            results_by_receptor[receptor_name].append(result)
    
    # Extract summary for each receptor (single prediction per receptor)
    summary_by_receptor = {}
    
    for receptor_name, receptor_results in results_by_receptor.items():
        receptor_summary = {}
        
        # Since we only have 1 prediction per receptor, just extract the values directly
        if receptor_results and receptor_results[0]["status"] == "completed":
            result = receptor_results[0]
            affinity = result.get("affinity_scores", {})
            confidence = result.get("confidence_scores", {})
            
            # Extract affinity metrics
            if "ic50_nM" in affinity:
                receptor_summary["ic50_nM"] = affinity["ic50_nM"]
                receptor_summary["ic50_uM"] = affinity.get("ic50_uM")
                receptor_summary["pic50"] = affinity.get("pic50")
                
                # Classify binding strength based on IC50
                ic50 = affinity["ic50_nM"]
                if ic50 < 10:
                    receptor_summary["binding_classification"] = "Very Strong Binder"
                elif ic50 < 100:
                    receptor_summary["binding_classification"] = "Strong Binder"
                elif ic50 < 1000:
                    receptor_summary["binding_classification"] = "Moderate Binder"
                elif ic50 < 10000:
                    receptor_summary["binding_classification"] = "Weak Binder"
                else:
                    receptor_summary["binding_classification"] = "Very Weak Binder"
            
            if "kd_nM" in affinity:
                receptor_summary["kd_nM"] = affinity["kd_nM"]
                receptor_summary["kd_uM"] = affinity.get("kd_uM")
                receptor_summary["pkd"] = affinity.get("pkd")
            
            if "delta_g_kcal" in affinity:
                receptor_summary["delta_g_kcal"] = affinity["delta_g_kcal"]
            
            if "boltz_affinity_value" in affinity:
                receptor_summary["boltz_affinity_value"] = affinity["boltz_affinity_value"]
                receptor_summary["affinity_prob"] = affinity.get("affinity_probability_binary")
            
            # Extract confidence metrics
            if "confidence_score" in confidence:
                receptor_summary["confidence_score"] = confidence["confidence_score"]
            if "ptm" in confidence:
                receptor_summary["ptm"] = confidence["ptm"]
            if "iptm" in confidence:
                receptor_summary["iptm"] = confidence["iptm"]
            if "plddt" in confidence:
                receptor_summary["plddt"] = confidence["plddt"]
            
            receptor_summary["status"] = "completed"
        else:
            receptor_summary["status"] = "failed" if receptor_results else "no_data"
            if receptor_results and receptor_results[0].get("error"):
                receptor_summary["error"] = receptor_results[0]["error"]
        
        summary_by_receptor[receptor_name] = receptor_summary
    
    return {
        "ligand_smiles": request.ligand_smiles,
        "total_jobs": len(job_ids),
        "results_by_receptor": results_by_receptor,
        "summary_by_receptor": summary_by_receptor
    }





# ==================== Main Entry Point ====================


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
