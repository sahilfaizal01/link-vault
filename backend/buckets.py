from __future__ import annotations

"""Topic buckets tuned for ML/GPU engineering + career link hoarding."""

CANONICAL_BUCKETS = [
    "LinkedIn Profiles",
    "Job Links",
    "GPU Programming",
    "Inference Optimization",
    "Model Architecture",
    "Training",
    "Tips & Tricks",
    "Frameworks & Tools",
    "Papers & Research",
    "Blogs & Articles",
    "News & Announcements",
    "Career & Networking",
]

# More specific rules first (URL fragments checked before plain keywords).
BUCKET_RULES: list[tuple[str, list[str]]] = [
    ("LinkedIn Profiles", ["linkedin.com/in/", "linkedin.com/pub/"]),
    (
        "Job Links",
        [
            "linkedin.com/jobs/",
            "/jobs/",
            "greenhouse.io",
            "lever.co",
            "workday",
            "ashbyhq.com",
            "job posting",
            "we're hiring",
            "open role",
        ],
    ),
    (
        "Inference Optimization",
        [
            "inference",
            "serving",
            "vllm",
            "tensorrt",
            "onnx",
            "quantization",
            "kv cache",
            "speculative decoding",
            "latency",
            "throughput",
            "batching",
            "deployment",
        ],
    ),
    (
        "GPU Programming",
        [
            "gpu",
            "cuda",
            "rocm",
            "hip",
            "kernel",
            "warp",
            "shared memory",
            "simd",
            "mfma",
            "hsa",
            "metal",
            "opencl",
        ],
    ),
    (
        "Model Architecture",
        [
            "architecture",
            "transformer",
            "attention",
            "moe",
            "mixture of experts",
            "llama",
            "mistral",
            "gemma",
            "diffusion",
            "encoder",
            "decoder",
        ],
    ),
    (
        "Training",
        [
            "training",
            "fine-tun",
            "finetun",
            "pretrain",
            "pre-train",
            "rlhf",
            "dpo",
            "lora",
            "optimizer",
            "loss function",
            "backprop",
            "gradient",
        ],
    ),
    (
        "Papers & Research",
        [
            "arxiv.org",
            "openreview.net",
            "doi.org",
            "proceedings",
            "whitepaper",
            "research paper",
            "neurips",
            "icml",
            "iclr",
        ],
    ),
    (
        "Frameworks & Tools",
        [
            "pytorch",
            "jax",
            "triton",
            "huggingface",
            "deepspeed",
            "megatron",
            "iree",
            "mlir",
            "cmake",
            "benchmark",
        ],
    ),
    (
        "Tips & Tricks",
        [
            "tips",
            "trick",
            "cheatsheet",
            "how i ",
            "how to",
            "thread",
            "lessons learned",
            "pitfall",
            "debugging tip",
        ],
    ),
    (
        "News & Announcements",
        [
            "announce",
            "launch",
            "released",
            "introducing",
            "changelog",
            "version ",
            "partnership",
        ],
    ),
    (
        "Career & Networking",
        [
            "networking",
            "referral",
            "resume",
            "portfolio",
            "personal brand",
            "mentor",
        ],
    ),
]

DEFAULT_BUCKET = "Blogs & Articles"


def classify_bucket(url: str, text_blob: str, source_type: str) -> tuple[str, list[str]]:
    """Return (bucket, matched_tags) using URL + text heuristics."""
    combined = f"{url.lower()} {text_blob.lower()}"
    for bucket, signals in BUCKET_RULES:
        hits = [s for s in signals if s in combined]
        if hits:
            return bucket, hits[:5]

    if source_type == "linkedin_profile":
        return "LinkedIn Profiles", ["linkedin"]
    if source_type == "linkedin_job":
        return "Job Links", ["linkedin-jobs"]
    if source_type == "linkedin":
        return "Career & Networking", ["linkedin"]

    return DEFAULT_BUCKET, []
