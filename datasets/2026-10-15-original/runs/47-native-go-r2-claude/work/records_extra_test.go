package records

import (
	"errors"
	"io"
	"strings"
	"testing"
	"testing/iotest"
)

func ids(rs []Record) []string {
	out := []string{}
	for _, r := range rs {
		out = append(out, r.ID)
	}
	return out
}

func wantIDs(t *testing.T, in string, max int, want ...string) {
	t.Helper()
	r, err := ReadUnique(strings.NewReader(in), max)
	if err != nil || strings.Join(ids(r), "|") != strings.Join(want, "|") {
		t.Fatalf("got %q %v, want %q", ids(r), err, want)
	}
}

func wantErr(t *testing.T, rd io.Reader, max int) error {
	t.Helper()
	r, err := ReadUnique(rd, max)
	if err == nil || r != nil {
		t.Fatalf("want nil, error; got %v %v", r, err)
	}
	return err
}

func TestEmptyLinesAndCRLF(t *testing.T) {
	wantIDs(t, "\n{\"id\":\"a\",\"value\":1}\r\n\r\n\n{\"id\":\"b\",\"value\":2}\r", 100, "a", "b")
}

func TestEmptyStream(t *testing.T) {
	wantIDs(t, "", 0)
	wantIDs(t, "\n\r\n", 5)
}

func TestNegativeLimitOnEmptyStream(t *testing.T) {
	wantErr(t, strings.NewReader(""), -1)
}

func TestLongLine(t *testing.T) {
	line := `{"id":"big","value":1,"pad":"` + strings.Repeat("x", 70000) + `"}`
	wantIDs(t, line+"\n", 0, "big")
	wantIDs(t, line+"\r\n", len(line), "big")
	wantIDs(t, line, len(line), "big")
	wantErr(t, strings.NewReader(line+"\n"), len(line)-1)
	wantErr(t, strings.NewReader(line), len(line)-1)
}

func TestLimitBoundary(t *testing.T) {
	line := `{"id":"a","value":1}`
	wantIDs(t, line+"\r\n", len(line), "a")
	wantErr(t, strings.NewReader(line+"\r\n"), len(line)-1)
	wantErr(t, strings.NewReader(line+"\n     \n"), len(line)+1) // whitespace counts toward the limit; first line passes
	wantErr(t, strings.NewReader(line+"\n"+line+"x\n"), len(line))
}

func TestInvalidJSON(t *testing.T) {
	wantErr(t, strings.NewReader("{\"id\":\"a\",\"value\":1}\n{bad}\n"), 0)
	wantErr(t, strings.NewReader("{\"id\":\"a\"} {\"id\":\"b\"}\n"), 0)
	wantErr(t, strings.NewReader("   \n"), 0)
}

func TestBadID(t *testing.T) {
	wantErr(t, strings.NewReader("{\"value\":1}\n"), 0)
	wantErr(t, strings.NewReader("{\"id\":\" \\t\",\"value\":1}\n"), 0)
	wantErr(t, strings.NewReader("null\n"), 0)
}

func TestIDNotNormalized(t *testing.T) {
	wantIDs(t, "{\"id\":\" a \"}\n{\"id\":\"a\"}\n{\"id\":\" a \"}\n", 0, " a ", "a")
}

func TestOrderAndFirstWins(t *testing.T) {
	r, err := ReadUnique(strings.NewReader("{\"id\":\"b\",\"value\":1}\n{\"id\":\"a\",\"value\":2}\n{\"id\":\"b\",\"value\":3}\n"), 0)
	if err != nil || len(r) != 2 || r[0].ID != "b" || r[0].Value != 1 || r[1].ID != "a" {
		t.Fatalf("%v %v", r, err)
	}
}

func TestInvalidDuplicate(t *testing.T) {
	wantErr(t, strings.NewReader("{\"id\":\"a\",\"value\":1}\n{\"id\":\"a\",\"value\":\"x\"}\n"), 0)
}

func TestReaderError(t *testing.T) {
	boom := errors.New("boom")
	err := wantErr(t, io.MultiReader(strings.NewReader("{\"id\":\"a\"}\n"), iotest.ErrReader(boom)), 0)
	if !errors.Is(err, boom) {
		t.Fatalf("lost read error: %v", err)
	}
	// Error mid-line: the truncated line must not mask the read error.
	err = wantErr(t, io.MultiReader(strings.NewReader("{\"id\":\"a\",\"val"), iotest.ErrReader(boom)), 0)
	if !errors.Is(err, boom) {
		t.Fatalf("lost read error: %v", err)
	}
}
