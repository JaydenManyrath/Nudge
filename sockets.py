from app import socketio


@socketio.on("connect")
def handle_connect():
    pass


def emit_transcript_line(line):
    pass
