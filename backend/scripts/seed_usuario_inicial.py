"""Cria o primeiro usuário (papel master) para permitir o primeiro login.

Uso:
    python -m scripts.seed_usuario_inicial --email admin@pg.com --senha "TrocarDepois123!" --nome "Admin"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models.enums import PapelUsuario  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services.auth_service import hash_senha  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--senha", required=True)
    parser.add_argument("--nome", default="Administrador")
    parser.add_argument("--papel", default="master", choices=[p.value for p in PapelUsuario])
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if db.query(Usuario).filter(Usuario.email == args.email).first() is not None:
            print(f"Já existe um usuário com o email {args.email}. Nada a fazer.")
            return

        usuario = Usuario(
            nome=args.nome,
            email=args.email,
            senha_hash=hash_senha(args.senha),
            papel=PapelUsuario(args.papel),
        )
        db.add(usuario)
        db.commit()
        print(f"Usuário criado: {args.email} (papel={args.papel})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
