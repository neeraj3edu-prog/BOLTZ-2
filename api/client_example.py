"""Example Python client for Boltz API."""

import requests
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"


def submit_prediction(sequence: str) -> str:
    """Submit a prediction job."""
    response = requests.post(
        f"{BASE_URL}/predict",
        json={
            "sequences": [
                {"protein": {"id": "A", "sequence": sequence}}
            ],
            "use_msa_server": True,
            "diffusion_samples": 1,
        },
    )
    response.raise_for_status()
    return response.json()["job_id"]


def wait_for_completion(job_id: str, poll_interval: int = 10) -> dict:
    """Wait for job to complete."""
    while True:
        response = requests.get(f"{BASE_URL}/jobs/{job_id}/status")
        response.raise_for_status()
        status_data = response.json()
        
        print(f"Status: {status_data['status']}")
        
        if status_data["status"] in ["completed", "failed"]:
            return status_data
        
        time.sleep(poll_interval)


def get_results(job_id: str) -> dict:
    """Get job results."""
    response = requests.get(f"{BASE_URL}/jobs/{job_id}/result")
    response.raise_for_status()
    return response.json()


def download_file(job_id: str, file_path: str, output_path: Path):
    """Download output file."""
    response = requests.get(
        f"{BASE_URL}/jobs/{job_id}/download/{file_path}",
        stream=True,
    )
    response.raise_for_status()
    
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


if __name__ == "__main__":
    # Example usage
    sequence = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL"
    
    print("Submitting prediction...")
    job_id = submit_prediction(sequence)
    print(f"Job ID: {job_id}")
    
    print("\nWaiting for completion...")
    status = wait_for_completion(job_id)
    
    if status["status"] == "completed":
        print("\nGetting results...")
        results = get_results(job_id)
        print(f"Confidence: {results['confidence_scores']['confidence_score']:.4f}")
        
        # Download structure
        if results["predictions"]:
            output_file = Path("structure.cif")
            print(f"\nDownloading to {output_file}...")
            download_file(job_id, results["predictions"][0], output_file)
            print("Done!")
    else:
        print(f"\nJob failed: {status.get('error')}")
