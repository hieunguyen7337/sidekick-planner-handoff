# source this inside a PBS job; it only sets environment variables
# Do not run directly on the login node.

export PUBTOOLS=/scratch/n12194778/pubtools

# Prepend TinyTeX bin and pubtools shim bin if not already in PATH (order: $PUBTOOLS/bin then TinyTeX)
case ":$PATH:" in
  *":$PUBTOOLS/TinyTeX/bin/x86_64-linux:"*) ;;
  *) export PATH="$PUBTOOLS/TinyTeX/bin/x86_64-linux:$PATH" ;;
esac

case ":$PATH:" in
  *":$PUBTOOLS/bin:"*) ;;
  *) export PATH="$PUBTOOLS/bin:$PATH" ;;
esac

export PAPER_BUILD=/scratch/n12194778/paper_build
export PUBTOOLS_PY=/scratch/n12194778/sidekick/env/bin/python
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
