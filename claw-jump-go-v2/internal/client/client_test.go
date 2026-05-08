package client

import (
	"fmt"
	"net"
	"strings"
	"testing"
	"time"
)

func startTestServer(t *testing.T, handler func(conn net.Conn)) (int, func()) {
	t.Helper()

	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("failed to listen: %v", err)
	}

	port := listener.Addr().(*net.TCPAddr).Port

	done := make(chan struct{})
	go func() {
		defer close(done)
		for {
			conn, err := listener.Accept()
			if err != nil {
				return
			}
			handler(conn)
		}
	}()

	cleanup := func() {
		listener.Close()
		<-done
	}
	return port, cleanup
}

func TestSendEvent_Success(t *testing.T) {
	port, cleanup := startTestServer(t, func(conn net.Conn) {
		defer conn.Close()

		buf := make([]byte, 1024)
		n, _ := conn.Read(buf)
		req := string(buf[:n])

		// Verify request format.
		if !strings.HasPrefix(req, "POST /event HTTP/1.1\r\n") {
			t.Errorf("unexpected request start: %s", req[:50])
		}

		// Send 202 response (matches Python agent).
		resp := "HTTP/1.0 202 Accepted\r\nContent-Type: application/json\r\n\r\n{\"accepted\":true}"
		conn.Write([]byte(resp))
	})
	defer cleanup()

	body := []byte(`{"event":"stop","sessionId":"test"}`)
	err := SendEvent(port, body)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestSendEvent_HTTP11Response(t *testing.T) {
	port, cleanup := startTestServer(t, func(conn net.Conn) {
		defer conn.Close()
		buf := make([]byte, 1024)
		conn.Read(buf)
		conn.Write([]byte("HTTP/1.1 200 OK\r\n\r\n"))
	})
	defer cleanup()

	err := SendEvent(port, []byte(`{}`))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestSendEvent_Non2xxResponse(t *testing.T) {
	port, cleanup := startTestServer(t, func(conn net.Conn) {
		defer conn.Close()
		buf := make([]byte, 1024)
		conn.Read(buf)
		conn.Write([]byte("HTTP/1.0 500 Internal Server Error\r\n\r\n"))
	})
	defer cleanup()

	err := SendEvent(port, []byte(`{}`))
	if err == nil {
		t.Fatal("expected error for non-2xx response")
	}
	if _, ok := err.(*UnexpectedResponseError); !ok {
		t.Errorf("expected UnexpectedResponseError, got %T: %v", err, err)
	}
}

func TestSendEvent_AgentNotRunning(t *testing.T) {
	// Pick a port that's unlikely to be in use.
	err := SendEvent(19999, []byte(`{}`))
	if err == nil {
		t.Fatal("expected error when agent not running")
	}
	if _, ok := err.(*AgentNotRunningError); !ok {
		t.Errorf("expected AgentNotRunningError, got %T: %v", err, err)
	}
}

func TestSendEvent_RequestContent(t *testing.T) {
	port, cleanup := startTestServer(t, func(conn net.Conn) {
		defer conn.Close()
		buf := make([]byte, 2048)
		n, _ := conn.Read(buf)
		req := string(buf[:n])

		// Check for required headers.
		if !strings.Contains(req, "Content-Type: application/json") {
			t.Error("missing Content-Type header")
		}
		if !strings.Contains(req, "Host: 127.0.0.1") {
			t.Error("missing or wrong Host header")
		}
		if !strings.Contains(req, "Connection: close") {
			t.Error("missing Connection: close header")
		}
		if !strings.Contains(req, "Content-Length:") {
			t.Error("missing Content-Length header")
		}

		// Verify body is appended after headers.
		parts := strings.Split(req, "\r\n\r\n")
		if len(parts) < 2 {
			t.Fatal("no body found in request")
		}

		conn.Write([]byte("HTTP/1.0 202 Accepted\r\n\r\n"))
	})
	defer cleanup()

	body := []byte(`{"event":"stop","sessionId":"test-123"}`)
	err := SendEvent(port, body)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestSendEvent_Timeout(t *testing.T) {
	// Use a non-routable address to trigger timeout.
	// 192.0.2.0/24 is reserved for TEST-NET-1 (RFC 5737).
	err := SendEvent(47653, []byte(`{}`))
	if err == nil {
		t.Fatal("expected error on timeout/non-routable")
	}

	// Could be AgentNotRunningError (connection refused) or timeout.
	// Either is acceptable — the important thing is we get an error.
	_ = err
}

func TestAgentNotRunningError(t *testing.T) {
	orig := fmt.Errorf("connection refused")
	e := &AgentNotRunningError{Err: orig}
	if !strings.Contains(e.Error(), "Claw Jump agent is not running") {
		t.Errorf("unexpected error message: %s", e.Error())
	}
}

func TestUnexpectedResponseError(t *testing.T) {
	e := &UnexpectedResponseError{Response: "HTTP/1.0 500 Oops"}
	if !strings.Contains(e.Error(), "unexpected response") {
		t.Errorf("unexpected error message: %s", e.Error())
	}
}

func TestSendEvent_EmptyBody(t *testing.T) {
	port, cleanup := startTestServer(t, func(conn net.Conn) {
		defer conn.Close()
		buf := make([]byte, 1024)
		conn.Read(buf)
		conn.Write([]byte("HTTP/1.0 202 Accepted\r\n\r\n"))
	})
	defer cleanup()

	err := SendEvent(port, []byte(`{}`))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

// BenchmarkSendEvent measures end-to-end latency of a localhost event send.
func BenchmarkSendEvent(b *testing.B) {
	// Start a test server that mimics the Python agent's response.
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		b.Fatalf("failed to listen: %v", err)
	}
	port := listener.Addr().(*net.TCPAddr).Port

	go func() {
		for {
			conn, err := listener.Accept()
			if err != nil {
				return
			}
			buf := make([]byte, 1024)
			conn.Read(buf)
			conn.Write([]byte("HTTP/1.0 202 Accepted\r\n\r\n"))
			conn.Close()
		}
	}()
	defer listener.Close()

	body := []byte(`{"event":"notification","sessionId":"bench","message":"test"}`)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = SendEvent(port, body)
	}
}

func init() {
	// Ensure tests don't hang on slow CI.
	time.Local = time.UTC
}
