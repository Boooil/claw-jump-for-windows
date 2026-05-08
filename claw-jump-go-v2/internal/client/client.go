package client

import (
	"fmt"
	"net"
	"strings"
	"time"
)

// SendEvent POSTs a JSON body to the agent's /event endpoint using a raw
// TCP socket. This deliberately avoids net/http to minimise cold-start
// overhead, matching the Python claw_jump_common.py approach.
//
// Returns nil on success (HTTP 2xx). Returns error if the agent is
// unreachable, the connection times out, or the response is not 2xx.
func SendEvent(port int, body []byte) error {
	addr := fmt.Sprintf("127.0.0.1:%d", port)

	conn, err := net.DialTimeout("tcp", addr, 2*time.Second)
	if err != nil {
		return &AgentNotRunningError{Err: err}
	}
	defer conn.Close()

	// Set a deadline for the entire exchange.
	conn.SetDeadline(time.Now().Add(2 * time.Second))

	// Construct the HTTP request manually — must match the Python version:
	//   POST /event HTTP/1.1
	//   Host: 127.0.0.1:{port}
	//   Content-Type: application/json
	//   Content-Length: {len}
	//   Connection: close
	req := fmt.Sprintf(
		"POST /event HTTP/1.1\r\n"+
			"Host: %s\r\n"+
			"Content-Type: application/json\r\n"+
			"Content-Length: %d\r\n"+
			"Connection: close\r\n"+
			"\r\n",
		addr, len(body),
	)

	data := append([]byte(req), body...)
	if _, err := conn.Write(data); err != nil {
		return fmt.Errorf("failed to send request: %w", err)
	}

	// Read response.
	resp := make([]byte, 512)
	n, err := conn.Read(resp)
	if err != nil {
		return fmt.Errorf("failed to read response: %w", err)
	}

	respStr := string(resp[:n])
	if !strings.HasPrefix(respStr, "HTTP/1.0 2") && !strings.HasPrefix(respStr, "HTTP/1.1 2") {
		return &UnexpectedResponseError{Response: respStr}
	}

	return nil
}

// AgentNotRunningError is returned when the agent cannot be reached.
type AgentNotRunningError struct {
	Err error
}

func (e *AgentNotRunningError) Error() string {
	return fmt.Sprintf("Claw Jump agent is not running: %v", e.Err)
}

// UnexpectedResponseError is returned when the agent returns a non-2xx status.
type UnexpectedResponseError struct {
	Response string
}

func (e *UnexpectedResponseError) Error() string {
	return fmt.Sprintf("agent returned an unexpected response: %s", e.Response)
}
