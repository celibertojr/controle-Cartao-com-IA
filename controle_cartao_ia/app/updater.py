"""
Verificação e aplicação de atualizações via GitHub.

Fluxo:
  1. Lê o SHA do commit local com `git rev-parse HEAD`
  2. Consulta a GitHub API para obter o SHA do último commit no main
  3. Se forem diferentes, oferece atualização
  4. Aplica com `git pull` e reinicia o app
"""

import json
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

from .utils import PROJECT_ROOT

GITHUB_REPO   = "celibertojr/controle-Cartao-com-IA"
GITHUB_BRANCH = "main"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/commits/{GITHUB_BRANCH}"


def local_commit() -> str:
    """Retorna o SHA completo do commit atual."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT), timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def local_commit_date() -> str:
    """Retorna a data do commit atual no formato AAAA-MM-DD."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ci"],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT), timeout=10,
        )
        return result.stdout.strip()[:10]
    except Exception:
        return "desconhecida"


def remote_info() -> dict:
    """
    Consulta a GitHub API e retorna dict com:
      sha, message, date
    Lança exceção em caso de falha de rede ou resposta inválida.
    """
    req = Request(API_URL, headers={"User-Agent": "controle-cartao-app/1.0"})
    with urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode())
    return {
        "sha":     data["sha"],
        "message": data["commit"]["message"].split("\n")[0],
        "date":    data["commit"]["author"]["date"][:10],
    }


def check_update() -> dict:
    """
    Verifica se há atualização disponível.
    Retorna dict:
      {
        "has_update": bool,
        "local_sha":  str,
        "remote_sha": str,
        "remote_message": str,
        "remote_date": str,
        "error": str | None,
      }
    """
    local = local_commit()
    try:
        remote = remote_info()
    except URLError as e:
        return {"has_update": False, "local_sha": local, "remote_sha": "",
                "remote_message": "", "remote_date": "", "error": f"Sem conexão: {e.reason}"}
    except Exception as e:
        return {"has_update": False, "local_sha": local, "remote_sha": "",
                "remote_message": "", "remote_date": "", "error": str(e)}

    return {
        "has_update":      local != remote["sha"],
        "local_sha":       local,
        "remote_sha":      remote["sha"],
        "remote_message":  remote["message"],
        "remote_date":     remote["date"],
        "error":           None,
    }


def apply_update() -> tuple[bool, str]:
    """
    Executa `git pull` no diretório do projeto.
    Retorna (sucesso: bool, mensagem: str).
    """
    try:
        result = subprocess.run(
            ["git", "pull"],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT), timeout=60,
        )
        if result.returncode == 0:
            return True, result.stdout.strip() or "Atualização aplicada."
        return False, result.stderr.strip() or "Erro desconhecido no git pull."
    except FileNotFoundError:
        return False, "git não encontrado. Verifique se o Git está instalado e no PATH."
    except subprocess.TimeoutExpired:
        return False, "Tempo limite excedido durante o git pull."
    except Exception as e:
        return False, str(e)


def restart_app():
    """Reinicia o aplicativo lançando um novo processo e encerrando o atual."""
    main_script = PROJECT_ROOT / "main.py"
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = str(pythonw) if pythonw.exists() else sys.executable
    subprocess.Popen([executable, str(main_script)], cwd=str(PROJECT_ROOT))
    sys.exit(0)
