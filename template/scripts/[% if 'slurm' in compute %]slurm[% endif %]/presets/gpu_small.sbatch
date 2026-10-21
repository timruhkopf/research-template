#!/bin/bash
# Resource header only. Account/partition come from SBATCH_ACCOUNT / SBATCH_PARTITION in .env.
# --signal: USR1 two minutes before the time limit; members checkpoint, and the element requeues itself.
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --signal=B:USR1@120
#SBATCH --requeue
exec "$@"
