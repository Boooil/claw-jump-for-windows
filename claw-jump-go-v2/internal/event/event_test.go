package event

import (
	"encoding/json"
	"os"
	"testing"
)

func TestBuildFromHookJSON_StopEvent(t *testing.T) {
	input := []byte(`{
		"session_id": "sess-123",
		"cwd": "/home/user/project",
		"transcript_path": "/tmp/transcript.json",
		"hook_event_name": "Stop",
		"source_app": "iTerm"
	}`)

	p, err := BuildFromHookJSON(EventStop, input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if p == nil {
		t.Fatal("expected non-nil payload")
	}

	if p.Event != EventStop {
		t.Errorf("Event = %q, want %q", p.Event, EventStop)
	}
	if p.SessionID != "sess-123" {
		t.Errorf("SessionID = %q, want sess-123", p.SessionID)
	}
	if p.CWD != "/home/user/project" {
		t.Errorf("CWD = %q", p.CWD)
	}
	if p.TranscriptPath != "/tmp/transcript.json" {
		t.Errorf("TranscriptPath = %q", p.TranscriptPath)
	}
	if p.SourceApp != "iTerm" {
		t.Errorf("SourceApp = %q, want iTerm", p.SourceApp)
	}
	if p.Platform == "" {
		t.Error("Platform should not be empty")
	}
	if p.Timestamp == "" {
		t.Error("Timestamp should not be empty")
	}
}

func TestBuildFromHookJSON_NotificationEvent(t *testing.T) {
	input := []byte(`{
		"session_id": "sess-456",
		"message": "Claude needs your approval",
		"hook_event_name": "Notification"
	}`)

	p, err := BuildFromHookJSON(EventNotification, input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if p == nil {
		t.Fatal("expected non-nil payload")
	}

	if p.Event != EventNotification {
		t.Errorf("Event = %q, want %q", p.Event, EventNotification)
	}
	if p.Message != "Claude needs your approval" {
		t.Errorf("Message = %q, want 'Claude needs your approval'", p.Message)
	}
}

func TestBuildFromHookJSON_NotificationWithoutMessage(t *testing.T) {
	input := []byte(`{"session_id": "sess-789", "hook_event_name": "Notification"}`)

	p, err := BuildFromHookJSON(EventNotification, input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if p.Message != "" {
		t.Errorf("Message = %q, want empty", p.Message)
	}
}

func TestBuildFromHookJSON_EmptyInput(t *testing.T) {
	p, err := BuildFromHookJSON(EventStop, nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if p != nil {
		t.Error("expected nil payload for empty input")
	}

	p, err = BuildFromHookJSON(EventStop, []byte{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if p != nil {
		t.Error("expected nil payload for empty input")
	}
}

func TestBuildFromHookJSON_InvalidJSON(t *testing.T) {
	p, err := BuildFromHookJSON(EventStop, []byte("not json"))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if p != nil {
		t.Error("expected nil payload for invalid JSON")
	}
}

func TestBuildFromHookJSON_WhitespaceOnly(t *testing.T) {
	// Python version strips and exits if empty after strip.
	// Our Go version parses as JSON; whitespace-only is invalid JSON → nil.
	p, err := BuildFromHookJSON(EventStop, []byte("   \n  "))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// "   \n  " is not valid JSON, so returns nil.
	if p != nil {
		t.Error("expected nil payload for whitespace-only input")
	}
}

func TestBuildFromHookJSON_SourceAppFallback(t *testing.T) {
	os.Setenv("TERM_PROGRAM", "WezTerm")
	defer os.Unsetenv("TERM_PROGRAM")

	// No source_app in JSON → fallback to TERM_PROGRAM env.
	input := []byte(`{"session_id": "abc"}`)
	p, err := BuildFromHookJSON(EventStop, input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if p.SourceApp != "WezTerm" {
		t.Errorf("SourceApp = %q, want WezTerm (from TERM_PROGRAM)", p.SourceApp)
	}
}

func TestBuildFromHookJSON_TerminalEnvVars(t *testing.T) {
	os.Setenv("CLAW_JUMP_TTY", "/dev/ttys005")
	os.Setenv("TERM_SESSION_ID", "ts-001")
	defer os.Unsetenv("CLAW_JUMP_TTY")
	defer os.Unsetenv("TERM_SESSION_ID")

	input := []byte(`{"session_id": "abc"}`)
	p, err := BuildFromHookJSON(EventStop, input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if p.TerminalTTY != "/dev/ttys005" {
		t.Errorf("TerminalTTY = %q, want /dev/ttys005", p.TerminalTTY)
	}
	if p.TerminalSessionID != "ts-001" {
		t.Errorf("TerminalSessionID = %q, want ts-001", p.TerminalSessionID)
	}
}

func TestBuildFromHookJSON_ITermSessionIDFallback(t *testing.T) {
	os.Setenv("ITERM_SESSION_ID", "iterm-sess-99")
	defer os.Unsetenv("ITERM_SESSION_ID")

	input := []byte(`{"session_id": "abc"}`)
	p, err := BuildFromHookJSON(EventStop, input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if p.TerminalSessionID != "iterm-sess-99" {
		t.Errorf("TerminalSessionID = %q, want iterm-sess-99", p.TerminalSessionID)
	}
}

func TestBuildFromHookJSON_PermissionRequestEvent(t *testing.T) {
	input := []byte(`{
		"session_id": "sess-pr-001",
		"cwd": "/home/user/project",
		"transcript_path": "/tmp/transcript.json",
		"hook_event_name": "PermissionRequest",
		"tool_name": "Bash",
		"tool_input": {"command": "rm -rf /"}
	}`)

	p, err := BuildFromHookJSON(EventPermissionRequest, input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if p == nil {
		t.Fatal("expected non-nil payload")
	}

	if p.Event != EventPermissionRequest {
		t.Errorf("Event = %q, want %q", p.Event, EventPermissionRequest)
	}
	if p.SessionID != "sess-pr-001" {
		t.Errorf("SessionID = %q, want sess-pr-001", p.SessionID)
	}
	if p.CWD != "/home/user/project" {
		t.Errorf("CWD = %q", p.CWD)
	}
	if p.TranscriptPath != "/tmp/transcript.json" {
		t.Errorf("TranscriptPath = %q", p.TranscriptPath)
	}
	if p.HookEventName != "PermissionRequest" {
		t.Errorf("HookEventName = %q, want PermissionRequest", p.HookEventName)
	}
	if p.Message != "" {
		t.Errorf("Message = %q, want empty (permission_request does not extract message)", p.Message)
	}
}

func TestBuildEmitPayload(t *testing.T) {
	p := BuildEmitPayload(EventTest)
	if p.Event != EventTest {
		t.Errorf("Event = %q, want %q", p.Event, EventTest)
	}
	if p.SourceApp != "cli" {
		t.Errorf("SourceApp = %q, want cli", p.SourceApp)
	}
}

func TestPayloadMarshal(t *testing.T) {
	p := &Payload{
		Event:     EventStop,
		SessionID: "sess-1",
		SourceApp: "iTerm",
	}

	body, err := p.Marshal()
	if err != nil {
		t.Fatalf("Marshal error: %v", err)
	}

	var decoded map[string]any
	if err := json.Unmarshal(body, &decoded); err != nil {
		t.Fatalf("unmarshal back: %v", err)
	}

	if decoded["event"] != EventStop {
		t.Errorf("event = %v, want %v", decoded["event"], EventStop)
	}
	if decoded["sessionId"] != "sess-1" {
		t.Errorf("sessionId = %v, want sess-1", decoded["sessionId"])
	}
}

func TestPayloadMarshal_OmitEmptyMessage(t *testing.T) {
	p := &Payload{
		Event:     EventStop,
		SessionID: "sess-1",
		// Message is empty — should be omitted due to omitempty tag.
	}

	body, err := p.Marshal()
	if err != nil {
		t.Fatalf("Marshal error: %v", err)
	}

	var decoded map[string]any
	json.Unmarshal(body, &decoded)

	if _, ok := decoded["message"]; ok {
		t.Error("message field should be omitted when empty")
	}
}
