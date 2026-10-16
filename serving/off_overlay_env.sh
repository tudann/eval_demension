# Point server caches at the project tree on /keyan.
# The container root is an overlay; filling it restarts the machine.
# Source this file before launching a server process.
off_overlay_cache_root() {
  local root="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
  local cache="$root/.runtime/server-cache"
  mkdir -p \
    "$cache/home" \
    "$cache/tmp" \
    "$cache/xdg" \
    "$cache/hf/hub" \
    "$cache/hf/transformers" \
    "$cache/torch" \
    "$cache/sglang/triton" \
    "$cache/sglang/inductor" \
    "$cache/sglang/nv" \
    "$cache/sglang/tilelang" \
    "$cache/sglang/jit" \
    "$cache/mpl"
  export HOME="$cache/home"
  export TMPDIR="$cache/tmp"
  export TMP="$cache/tmp"
  export TEMP="$cache/tmp"
  export XDG_CACHE_HOME="$cache/xdg"
  export HF_HOME="$cache/hf"
  export HUGGINGFACE_HUB_CACHE="$cache/hf/hub"
  export TRANSFORMERS_CACHE="$cache/hf/transformers"
  export TORCH_HOME="$cache/torch"
  export SGLANG_CACHE_DIR="$cache/sglang"
  export TRITON_CACHE_DIR="$cache/sglang/triton"
  export TORCHINDUCTOR_CACHE_DIR="$cache/sglang/inductor"
  export CUDA_CACHE_PATH="$cache/sglang/nv"
  export TILELANG_CACHE_DIR="$cache/sglang/tilelang"
  export FLASHINFER_WORKSPACE_BASE="$cache/sglang"
  export MPLCONFIGDIR="$cache/mpl"
  export PYTHONDONTWRITEBYTECODE=1
}
