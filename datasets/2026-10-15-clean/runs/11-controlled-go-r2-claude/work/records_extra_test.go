package records

import (
	"errors"
	"io"
	"strings"
	"testing"
	"testing/iotest"
)

func TestSkipsEmptyLinesAndCRLF(t *testing.T) {
	in := "\r\n{\"id\":\"b\",\"value\":1}\r\n\n{\"id\":\"a\",\"value\":2}\r\n{\"id\":\"b\",\"value\":3}"
	r, e := ReadUnique(strings.NewReader(in), 0)
	if e != nil || len(r) != 2 || r[0].ID != "b" || r[0].Value != 1 || r[1].ID != "a" {
		t.Fatalf("%v %v", r, e)
	}
}

func TestEmptyStream(t *testing.T) {
	r, e := ReadUnique(strings.NewReader(""), 10)
	if e != nil || r == nil || len(r) != 0 {
		t.Fatalf("%v %v", r, e)
	}
	if r, e := ReadUnique(strings.NewReader(""), -1); e == nil || r != nil {
		t.Fatalf("negative limit: %v %v", r, e)
	}
}

func TestExactIDNotNormalized(t *testing.T) {
	r, e := ReadUnique(strings.NewReader("{\"id\":\"a\"}\n{\"id\":\" a\"}\n"), 0)
	if e != nil || len(r) != 2 || r[1].ID != " a" {
		t.Fatalf("%v %v", r, e)
	}
}

func TestErrorsReturnNil(t *testing.T) {
	for name, in := range map[string]string{
		"bad json":       "{\"id\":\"a\"}\n{bad}\n",
		"bad duplicate":  "{\"id\":\"a\"}\n{\"id\":\"a\",\"value\":\"x\"}\n",
		"missing id":     "{\"id\":\"a\"}\n{\"value\":1}\n",
		"blank id":       "{\"id\":\"a\"}\n{\"id\":\" \\t\"}\n",
		"trailing":       "{\"id\":\"a\"} {}\n",
		"whitespace row": "{\"id\":\"a\"}\n   \n",
	} {
		if r, e := ReadUnique(strings.NewReader(in), 0); e == nil || r != nil {
			t.Errorf("%s: %v %v", name, r, e)
		}
	}
}

func TestLimit(t *testing.T) {
	line := "{\"id\":\"a\"}" // 10 bytes
	if r, e := ReadUnique(strings.NewReader(line+"\r\n"), 10); e != nil || len(r) != 1 {
		t.Fatalf("exact: %v %v", r, e)
	}
	if r, e := ReadUnique(strings.NewReader(line+"\n"), 9); !errors.Is(e, ErrLineTooLong) || r != nil {
		t.Fatalf("over: %v %v", r, e)
	}
	if r, e := ReadUnique(strings.NewReader(line+"\n{\"id\":\"a\",\"value\":1}"), 10); !errors.Is(e, ErrLineTooLong) || r != nil {
		t.Fatalf("duplicate over: %v %v", r, e)
	}
}

func TestLongLine(t *testing.T) {
	id := strings.Repeat("x", 200<<10)
	in := "{\"id\":\"" + id + "\"}\n{\"id\":\"y\"}"
	r, e := ReadUnique(strings.NewReader(in), 0)
	if e != nil || len(r) != 2 || r[0].ID != id {
		t.Fatalf("len=%d %v", len(r), e)
	}
	if r, e := ReadUnique(strings.NewReader(in), 100<<10); !errors.Is(e, ErrLineTooLong) || r != nil {
		t.Fatalf("limit: %v", e)
	}
}

func TestReadError(t *testing.T) {
	boom := errors.New("boom")
	src := io.MultiReader(strings.NewReader("{\"id\":\"a\"}\n"), iotest.ErrReader(boom))
	if r, e := ReadUnique(src, 0); !errors.Is(e, boom) || r != nil {
		t.Fatalf("%v %v", r, e)
	}
	src = iotest.DataErrReader(strings.NewReader("{\"id\":\"a\"}"))
	if r, e := ReadUnique(src, 0); e != nil || len(r) != 1 {
		t.Fatalf("data+EOF: %v %v", r, e)
	}
}
