from app import socketio


@socketio.on("connect")
def handle_connect():
    # Sprint 2 stub: real-time client presence and transcript streaming
    # will be wired after Zoom RTMS ingestion is connected.
    return None


def emit_transcript_line(line):
    socketio.emit("transcript_line", line)
    return line
