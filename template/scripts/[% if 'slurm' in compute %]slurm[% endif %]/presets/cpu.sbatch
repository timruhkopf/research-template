#!/bin/bash
# Resource header only. Account/partition come from SBATCH_ACCOUNT / SBATCH_PARTITION in .env.
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --signal=B:USR1@120
#SBATCH --requeue
exec "$@"
