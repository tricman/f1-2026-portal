"""
CLI Script to Seed / Migrate Local JSON state into Google Cloud Firestore.
Usage:
    python -m src.repositories.seed_firestore [--project <PROJECT_ID>]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Fix stdout for Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.orchestrator_cli import load_dotenv_if_present, ROOT_DIR
load_dotenv_if_present()

from src.repositories.firestore_repository import FirestoreRepository
from src.repositories.local_repository import LocalJsonRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed F1 Showrunner Local State into GCP Firestore")
    parser.add_argument("--project", default=os.environ.get("GCP_PROJECT_ID"), help="GCP Project ID")
    args = parser.parse_args()

    project_id = args.project
    print(f"🚀 Iniciando migração para o Google Cloud Firestore (Projeto: {project_id or 'default'})...")

    try:
        remote_repo = FirestoreRepository(project_id=project_id)
        local_repo = LocalJsonRepository(ROOT_DIR)

        # 1. Migrate Canon Ledger
        print("\n[1/3] Migrando Canon Ledger...")
        canon = local_repo.get_canon_ledger()
        events_count = len(canon.get("events", []))
        remote_repo.save_canon_ledger(canon)
        print(f"  ✅ Canon Ledger migrado com sucesso ({events_count} eventos salvos).")

        # 2. Migrate Standings
        print("\n[2/3] Migrando Standings FIA...")
        standings = local_repo.get_standings()
        d_count = len(standings.get("drivers_standings", []))
        c_count = len(standings.get("constructors_standings", []))
        remote_repo.save_standings(standings)
        print(f"  ✅ Standings migrados com sucesso ({d_count} pilotos, {c_count} construtores).")

        # 3. Migrate Press Conferences (if any exist)
        print("\n[3/3] Migrando Coletivas de Imprensa da FIA...")
        pc_migrated = 0
        state_dir = ROOT_DIR / "data" / "state"
        for pc_file in sorted(state_dir.glob("press_conf_et*.json")):
            try:
                round_num = int(pc_file.stem.replace("press_conf_et", ""))
                pc_data = json.loads(pc_file.read_text(encoding="utf-8"))
                remote_repo.save_press_conference(round_num, pc_data)
                pc_migrated += 1
                print(f"  ✅ Coletiva Etapa {round_num} migrada ({pc_data.get('status')}).")
            except Exception as exc:
                print(f"  ⚠️ Falha ao migrar {pc_file.name}: {exc}")

        print("\n✨ Migração 100% concluída com sucesso no Google Cloud Firestore!")
        print("💡 Para ativar o Firestore no motor da aplicação, configure:")
        print("   STORAGE_BACKEND=firestore")

    except Exception as exc:
        print(f"\n❌ Erro durante a migração para o Firestore: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()

