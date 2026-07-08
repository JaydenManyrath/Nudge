from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from auth import manager_required
from backend.ingestion.transcript_loader import list_sample_transcripts, load_sample_transcript
from extraction import ExtractionError, create_draft_tasks_from_transcript

bp = Blueprint("upload", __name__, url_prefix="/upload")


@bp.route("/", methods=["GET"])
@manager_required
def upload_form():
    return render_template(
        "upload.html",
        sample_transcripts=list_sample_transcripts(),
    )


@bp.route("/", methods=["POST"])
@manager_required
def upload_transcript():
    title, transcript_text = _transcript_from_request()
    if not transcript_text:
        abort(400, "Provide transcript text, a .txt file, or a sample transcript.")

    try:
        result = create_draft_tasks_from_transcript(title, transcript_text)
    except ExtractionError as exc:
        abort(400, str(exc))

    task_count = len(result["tasks"])
    flash(
        f"Created {task_count} draft task{'s' if task_count != 1 else ''} "
        f"from {result['meeting'].title}.",
        "success",
    )
    return redirect(url_for("review.list_drafts"))


def _transcript_from_request():
    sample_name = request.form.get("sample_transcript", "").strip()
    if sample_name:
        try:
            transcript_text = load_sample_transcript(sample_name)
        except FileNotFoundError as exc:
            abort(400, str(exc))
        return _title_from_filename(sample_name), transcript_text

    uploaded_file = request.files.get("transcript_file")
    if uploaded_file and uploaded_file.filename:
        try:
            transcript_text = uploaded_file.read().decode("utf-8")
        except UnicodeDecodeError:
            abort(400, "Transcript files must be UTF-8 encoded.")
        title = request.form.get("title", "").strip() or _title_from_filename(
            uploaded_file.filename
        )
        return title, transcript_text

    title = request.form.get("title", "").strip() or "Pasted Transcript"
    return title, request.form.get("transcript_text", "")


def _title_from_filename(filename):
    return filename.rsplit("/", 1)[-1].rsplit(".", 1)[0].replace("_", " ").title()
