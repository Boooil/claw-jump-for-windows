// claw-jump-hook is the Go replacement for the Python hook scripts in
// portable/hooks/.  It reads Claude Code hook JSON from stdin, normalises
// it into a standard event payload, and POSTs it to the Claw Jump agent
// on 127.0.0.1:47653.
//
// Usage:
//
//	claw-jump-hook stop               # Stop hook (reads stdin)
//	claw-jump-hook reset              # UserPromptSubmit hook (reads stdin)
//	claw-jump-hook notification       # Notification hook (reads stdin)
//	claw-jump-hook permission_request # PermissionRequest hook (reads stdin)
//	claw-jump-hook working            # PreToolUse / PostToolUse hook (reads stdin)
//
//	claw-jump-hook emit <event>   # Send a simple event (no stdin)
//
//	claw-jump-hook --help         # Show this help
//
// Debug logging: set CLAW_JUMP_DEBUG=1 to write timestamps to %TEMP%/claw-jump-debug.log
//
// On success the binary exits 0 silently.  On failure it prints to stderr
// and exits non-zero (emit mode) or exits 0 silently (hook mode, matching
// the Python hooks' tolerant behaviour).
package main

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/boil/claw-jump-go-v2/internal/client"
	"github.com/boil/claw-jump-go-v2/internal/event"
)

var debugLog *os.File

func main() {
	args := os.Args[1:]

	if len(args) == 0 || (len(args) == 1 && (args[0] == "--help" || args[0] == "-h")) {
		printUsage()
		os.Exit(0)
	}

	if os.Getenv("CLAW_JUMP_DEBUG") != "" {
		initDebugLog()
		dbg("binary_start args=%v", args)
	}

	if args[0] == "emit" {
		os.Exit(runEmit(args[1:]))
	}

	os.Exit(runHook(args[0]))
}

func runHook(eventName string) int {
	// Validate event name.
	switch eventName {
	case event.EventStop, event.EventReset, event.EventNotification, event.EventPermissionRequest, event.EventWorking:
	default:
		fmt.Fprintf(os.Stderr, "Unknown event: %s\n", eventName)
		printUsage()
		return 1
	}

	t0 := time.Now()
	rawJSON, err := io.ReadAll(os.Stdin)
	if err != nil {
		dbg("stdin_read_error after=%.0fms err=%v", msSince(t0), err)
		return 0
	}
	dbg("stdin_read after=%.0fms len=%d", msSince(t0), len(rawJSON))

	payload, err := event.BuildFromHookJSON(eventName, rawJSON)
	if err != nil || payload == nil {
		dbg("parse_fail after=%.0fms", msSince(t0))
		return 0
	}
	dbg("parsed after=%.0fms event=%s session=%s", msSince(t0), payload.Event, payload.SessionID)

	body, err := payload.Marshal()
	if err != nil {
		return 0
	}
	dbg("marshal after=%.0fms body_len=%d", msSince(t0), len(body))

	sendErr := client.SendEvent(event.DefaultPort, body)
	dbg("send_done after=%.0fms err=%v", msSince(t0), sendErr)

	if debugLog != nil {
		debugLog.Close()
	}
	return 0
}

func runEmit(args []string) int {
	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, "Usage: claw-jump-hook emit <event>")
		return 1
	}

	t0 := time.Now()
	dbg("emit_start event=%s", args[0])

	eventName := args[0]
	payload := event.BuildEmitPayload(eventName)

	body, err := payload.Marshal()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to marshal payload: %v\n", err)
		return 1
	}

	err = client.SendEvent(event.DefaultPort, body)
	dbg("emit_send after=%.0fms err=%v", msSince(t0), err)

	if err != nil {
		switch err.(type) {
		case *client.AgentNotRunningError:
			fmt.Fprintln(os.Stderr, "Claw Jump agent is not running.")
		case *client.UnexpectedResponseError:
			fmt.Fprintln(os.Stderr, "Agent returned an unexpected response.")
		default:
			fmt.Fprintf(os.Stderr, "Failed to contact agent: %v\n", err)
		}
		return 1
	}

	return 0
}

// -- debug helpers --

func initDebugLog() {
	dir := os.TempDir()
	path := filepath.Join(dir, "claw-jump-debug.log")
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		return
	}
	debugLog = f
}

func dbg(format string, args ...any) {
	if debugLog == nil {
		return
	}
	ts := time.Now().Format("2006-01-02T15:04:05.000")
	msg := fmt.Sprintf(format, args...)
	fmt.Fprintf(debugLog, "[hook %s] %s\n", ts, msg)
}

func msSince(t time.Time) float64 {
	return float64(time.Since(t).Microseconds()) / 1000.0
}

func printUsage() {
	lines := []string{
		"claw-jump-hook — Claw Jump hook for Claude Code (Go)",
		"",
		"Usage:",
		"  claw-jump-hook stop            Send stop event (reads stdin)",
		"  claw-jump-hook reset           Send reset event (reads stdin)",
		"  claw-jump-hook notification    Send notification event (reads stdin)",
		"  claw-jump-hook permission_request Send permission request event (reads stdin)",
		"  claw-jump-hook working         Send working event (reads stdin)",
		"  claw-jump-hook emit <event>    Send a simple event (no stdin)",
		"  claw-jump-hook --help          Show this help",
		"",
		"Events:",
		"  stop           Claude Code finished its response",
		"  reset          User submitted a new prompt",
		"  notification   Claude Code needs user input or approval",
		"  permission_request Claude Code is requesting tool permission",
		"  working        Claude Code is executing a tool",
		"",
		"Examples:",
		"  echo '{\"session_id\":\"abc\"}' | claw-jump-hook stop",
		"  claw-jump-hook emit test",
		"",
		"Debug:",
		"  set CLAW_JUMP_DEBUG=1 to write timestamps to %TEMP%/claw-jump-debug.log",
	}
	fmt.Println(strings.Join(lines, "\n"))
}
