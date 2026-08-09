import json
import mimetypes
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type
from urllib.parse import parse_qs, quote, urlparse

from .preferences import preference_pair_key
from .schema import ALLOWED_WINNERS, REASON_FLAGS
from .utils import read_jsonl


REVIEW_INTERFACE_ID = "stringartio-preference-lab/review-app"
REVIEW_INTERFACE_SCHEMA_VERSION = 1


@dataclass
class ReviewStore:
    queue_path: Path
    preference_path: Path
    artifact_roots: List[Path]
    reviewer: str = "local-review-ui"
    title: str = "StringArtio blind preference review"
    lock: threading.Lock = field(default_factory=threading.Lock)

    def queue_rows(self) -> List[Dict[str, Any]]:
        return read_jsonl(self.queue_path)

    def preference_rows(self) -> List[Dict[str, Any]]:
        return read_jsonl(self.preference_path)

    def existing_pair_keys(self) -> set:
        return {
            preference_pair_key(
                str(row.get("source_id") or ""),
                str(row.get("candidate_a") or ""),
                str(row.get("candidate_b") or ""),
            )
            for row in self.preference_rows()
        }

    def save(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        with self.lock:
            queue_id = str(payload.get("queue_id") or "")
            row = {str(item.get("queue_id")): item for item in self.queue_rows()}.get(queue_id)
            if not row:
                return 404, {"error": "unknown_queue_id"}
            winner = str(payload.get("winner") or "")
            if winner not in ALLOWED_WINNERS:
                return 400, {"error": "invalid_winner"}
            reason_flags = payload.get("reason_flags") or []
            if not isinstance(reason_flags, list):
                return 400, {"error": "invalid_reason_flags"}
            reason_flags = sorted({str(flag) for flag in reason_flags if str(flag) in REASON_FLAGS})
            pair_key = preference_pair_key(
                str(row.get("source_id") or ""),
                str(row.get("candidate_a") or ""),
                str(row.get("candidate_b") or ""),
            )
            if pair_key in self.existing_pair_keys():
                return 409, {"error": "pair_already_labeled"}
            record = {
                "preference_id": make_preference_id(queue_id),
                "source_id": row.get("source_id"),
                "candidate_a": row.get("candidate_a"),
                "candidate_b": row.get("candidate_b"),
                "winner": winner,
                "reviewer": self.reviewer,
                "timestamp": utc_now_iso(),
                "reason_flags": reason_flags,
                "review_context": {
                    "interface": REVIEW_INTERFACE_ID,
                    "interface_schema_version": REVIEW_INTERFACE_SCHEMA_VERSION,
                    "queue_id": queue_id,
                    "blind_first": True,
                },
            }
            notes = str(payload.get("notes") or "").strip()
            if notes:
                record["notes"] = notes
            self.preference_path.parent.mkdir(parents=True, exist_ok=True)
            with self.preference_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True))
                handle.write("\n")
            return 200, {"saved": True, "record": record}

    def artifact_path(self, raw_path: str) -> Optional[Path]:
        if not raw_path:
            return None
        try:
            path = Path(raw_path).resolve()
        except OSError:
            return None
        roots = [root.resolve() for root in self.artifact_roots]
        if not any(path == root or root in path.parents for root in roots):
            return None
        return path if path.is_file() else None

    def queue_payload(self) -> Dict[str, Any]:
        saved = self.existing_pair_keys()
        rows = []
        for row in self.queue_rows():
            blind = row.get("blind_artifacts") or {}
            diagnostic = row.get("diagnostic_artifacts") or {}
            key = preference_pair_key(
                str(row.get("source_id") or ""),
                str(row.get("candidate_a") or ""),
                str(row.get("candidate_b") or ""),
            )
            rows.append(
                {
                    **row,
                    "saved": key in saved,
                    "blind_artifact_urls": {side: artifact_url(blind.get(side)) for side in ("A", "B")},
                    "diagnostic_artifact_urls": {
                        side: artifact_url(diagnostic.get(side)) for side in ("A", "B")
                    },
                }
            )
        return {
            "title": self.title,
            "queue_path": str(self.queue_path),
            "preference_path": str(self.preference_path),
            "reason_flags": sorted(REASON_FLAGS),
            "rows": rows,
        }


def run_review_server(
    store: ReviewStore,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(store))
    print(f"http://{host}:{port}", flush=True)
    server.serve_forever()


def make_handler(store: ReviewStore) -> Type[BaseHTTPRequestHandler]:
    class ReviewHandler(BaseHTTPRequestHandler):
        server_version = "StringArtioPreferenceReview/2.0"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                return self.send_bytes(200, "text/html; charset=utf-8", PAGE_HTML.encode("utf-8"))
            if parsed.path == "/api/queue":
                return self.send_json(200, store.queue_payload())
            if parsed.path == "/artifact":
                raw_path = (parse_qs(parsed.query).get("path") or [""])[0]
                path = store.artifact_path(raw_path)
                if path is None:
                    return self.send_error(404)
                mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
                if path.suffix.lower() == ".svg":
                    mime_type = "image/svg+xml"
                return self.send_bytes(200, mime_type, path.read_bytes())
            self.send_error(404)

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/preference":
                return self.send_error(404)
            try:
                length = int(self.headers.get("Content-Length") or "0")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                return self.send_json(400, {"error": "invalid_json"})
            status, body = store.save(payload)
            self.send_json(status, body)

        def send_json(self, status: int, payload: Dict[str, Any]) -> None:
            self.send_bytes(
                status,
                "application/json; charset=utf-8",
                json.dumps(payload).encode("utf-8"),
            )

        def send_bytes(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ReviewHandler


def make_preference_id(queue_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ%f")
    suffix = "".join(character for character in queue_id if character.isalnum())[-8:] or "review"
    return f"pref-{stamp}-{suffix}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def artifact_url(raw_path: Optional[str]) -> str:
    return "" if not raw_path else "/artifact?path=" + quote(str(raw_path))


PAGE_HTML = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Blind preference review</title><style>
:root{color-scheme:light dark;font:15px system-ui}body{margin:0;background:#f3f4f6;color:#171717}main{max-width:1500px;margin:auto;padding:20px}header{position:sticky;top:0;background:#f3f4f6;padding:12px 0;z-index:2}.pair{background:white;border:1px solid #ddd;border-radius:12px;padding:16px;margin:18px 0}.pair.saved{border-color:#248447}.compare{display:grid;grid-template-columns:1fr 1fr;gap:16px}.image{background:white;min-height:360px;display:grid;place-items:center;border:1px solid #ddd}.image img{width:100%;height:min(65vh,680px);object-fit:contain}.choices,.flags{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.hidden{display:none}label{border:1px solid #ccc;border-radius:7px;padding:7px}textarea{width:100%;min-height:60px}button{padding:9px 16px}details{margin-top:12px}code{font-size:11px;overflow-wrap:anywhere}@media(max-width:800px){.compare{grid-template-columns:1fr}}@media(prefers-color-scheme:dark){body,header{background:#111;color:#eee}.pair{background:#1b1b1b;border-color:#444}label{border-color:#555}}
</style></head><body><main><header><h1 id="title">Blind preference review</h1><span id="status"></span></header><div id="pairs"></div></main>
<script>
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let state={rows:[],reason_flags:[]};
function card(r,i){const d=r.saved?'disabled':'';return `<section class="pair ${r.saved?'saved':''}" data-id="${esc(r.queue_id)}"><h2>${i+1}. ${esc(r.source_id)} ${r.saved?'✓':''}</h2><div class="compare">${['A','B'].map(s=>`<article><h3>${s}</h3><div class="image"><img src="${esc(r.blind_artifact_urls[s])}" alt="candidate ${s}"></div><code>${esc(r['candidate_'+s.toLowerCase()])}</code></article>`).join('')}</div><form><div class="choices">${['A','B','tie','both_bad'].map(w=>`<label><input type="radio" name="winner" value="${w}" ${d}>${w}</label>`).join('')}</div><div class="post-choice hidden"><div class="flags">${state.reason_flags.map(f=>`<label><input type="checkbox" name="flag" value="${esc(f)}" ${d}>${esc(f)}</label>`).join('')}</div><textarea name="notes" placeholder="optional note" ${d}></textarea></div><button ${d}>Save</button><span class="message"></span></form><details class="post-choice hidden"><summary>Diagnostics after blind choice</summary>${['A','B'].map(s=>`<a target="_blank" href="${esc(r.diagnostic_artifact_urls[s])}">${s} diagnostic</a> `).join('')}</details></section>`}
function render(){document.querySelector('#pairs').innerHTML=state.rows.map(card).join('');document.querySelector('#status').textContent=`${state.rows.filter(r=>r.saved).length}/${state.rows.length} saved`;document.querySelectorAll('form').forEach(f=>{f.onsubmit=save;f.querySelectorAll('[name=winner]').forEach(w=>w.onchange=()=>f.closest('.pair').querySelectorAll('.post-choice').forEach(x=>x.classList.remove('hidden')))})}
async function save(e){e.preventDefault();const f=e.currentTarget,s=f.closest('.pair'),w=f.querySelector('[name=winner]:checked'),m=f.querySelector('.message');if(!w){m.textContent=' choose an outcome';return}const body={queue_id:s.dataset.id,winner:w.value,reason_flags:[...f.querySelectorAll('[name=flag]:checked')].map(x=>x.value),notes:f.notes.value};const r=await fetch('/api/preference',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok){m.textContent=` ${data.error}`;return}state.rows.find(x=>x.queue_id===s.dataset.id).saved=true;render()}
fetch('/api/queue').then(r=>r.json()).then(data=>{state=data;document.querySelector('#title').textContent=data.title;render()});
</script></body></html>"""
