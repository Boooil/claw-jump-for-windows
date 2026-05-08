package event

import (
	"encoding/json"
	"os"
	"runtime"
	"time"
)

// Event names matching the Python claw_jump_common.py protocol.
const (
	EventStop              = "stop"
	EventReset             = "reset"
	EventNotification      = "notification"
	EventPermissionRequest = "permission_request"
	EventWorking           = "working"
	EventTest              = "test"
)

// DefaultPort is the default agent HTTP port.
const DefaultPort = 47653

// Payload is the JSON body sent to the agent's POST /event endpoint.
// Field names use the same camelCase convention as the Python version.
type Payload struct {
	Event             string `json:"event"`
	SessionID         string `json:"sessionId"`
	CWD               string `json:"cwd"`
	TranscriptPath    string `json:"transcriptPath"`
	HookEventName     string `json:"hookEventName"`
	SourceApp         string `json:"sourceApp"`
	TerminalTTY       string `json:"terminalTTY"`
	TerminalSessionID string `json:"terminalSessionId"`
	Timestamp         string `json:"timestamp"`
	Platform          string `json:"platform"`
	Message           string `json:"message,omitempty"`
}

// BuildFromHookJSON parses raw hook JSON from Claude Code stdin and
// constructs a normalized event payload. It replicates the logic in
// portable/hooks/claw_jump_common.py:send_event().
func BuildFromHookJSON(eventName string, rawJSON []byte) (*Payload, error) {
	if len(rawJSON) == 0 {
		return nil, nil
	}

	var hook map[string]any
	if err := json.Unmarshal(rawJSON, &hook); err != nil {
		return nil, nil // match Python: silently exit on bad JSON
	}

	p := &Payload{
		Event:             eventName,
		SessionID:          stringField(hook, "session_id"),
		CWD:                stringField(hook, "cwd"),
		TranscriptPath:     stringField(hook, "transcript_path"),
		HookEventName:      stringField(hook, "hook_event_name"),
		SourceApp:          stringField(hook, "source_app"),
		TerminalTTY:        os.Getenv("CLAW_JUMP_TTY"),
		TerminalSessionID:  firstNonEmpty(os.Getenv("TERM_SESSION_ID"), os.Getenv("ITERM_SESSION_ID")),
		Timestamp:          time.Now().Format(time.RFC3339),
		Platform:           runtime.GOOS,
	}

	// Fallback: sourceApp from TERM_PROGRAM env if not in hook JSON.
	if p.SourceApp == "" {
		p.SourceApp = os.Getenv("TERM_PROGRAM")
	}

	// Notification hook includes the user-facing message.
	if eventName == EventNotification {
		p.Message = stringField(hook, "message")
	}

	return p, nil
}

// BuildEmitPayload creates a minimal payload for CLI emit mode, matching
// the Python _emit_event() function.
func BuildEmitPayload(eventName string) *Payload {
	return &Payload{
		Event:     eventName,
		SourceApp: "cli",
	}
}

// Marshal serializes the payload to JSON bytes.
func (p *Payload) Marshal() ([]byte, error) {
	return json.Marshal(p)
}

func stringField(m map[string]any, key string) string {
	v, ok := m[key]
	if !ok {
		return ""
	}
	s, ok := v.(string)
	if !ok {
		return ""
	}
	return s
}

func firstNonEmpty(a, b string) string {
	if a != "" {
		return a
	}
	return b
}
