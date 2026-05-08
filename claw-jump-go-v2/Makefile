.PHONY: all build test clean cross-compile

# Default target: build the hook binary for the current platform.
all: build

# Build hook binary for the current OS/arch.
build:
	go build -ldflags="-s -w" -o bin/claw-jump-hook ./cmd/hook/

# Build hook binary with race detector (for development).
build-race:
	go build -race -o bin/claw-jump-hook ./cmd/hook/

# Run all tests.
test:
	go test -v -count=1 ./internal/...

# Run tests with race detector.
test-race:
	go test -race -v -count=1 ./internal/...

# Run benchmarks.
bench:
	go test -bench=. -benchmem ./internal/...

# Cross-compile for all target platforms.
cross-compile:
	GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o bin/claw-jump-hook-windows-amd64.exe ./cmd/hook/
	GOOS=darwin  GOARCH=amd64 go build -ldflags="-s -w" -o bin/claw-jump-hook-darwin-amd64      ./cmd/hook/
	GOOS=darwin  GOARCH=arm64 go build -ldflags="-s -w" -o bin/claw-jump-hook-darwin-arm64       ./cmd/hook/
	GOOS=linux   GOARCH=amd64 go build -ldflags="-s -w" -o bin/claw-jump-hook-linux-amd64        ./cmd/hook/
	GOOS=linux   GOARCH=arm64 go build -ldflags="-s -w" -o bin/claw-jump-hook-linux-arm64         ./cmd/hook/

# Clean build artifacts.
clean:
	rm -rf bin/

# Show binary size.
size:
	ls -lh bin/

# Run the test suite with coverage.
coverage:
	go test -coverprofile=coverage.out ./internal/...
	go tool cover -func=coverage.out
