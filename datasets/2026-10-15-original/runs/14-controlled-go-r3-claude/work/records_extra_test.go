package records

import (
	"errors"
	"io"
	"strings"
	"testing"
	"testing/iotest"
)

func TestEmptyLinesAndCRLF(t *testing.T) {
	in := "\n\r\n{\"id\":\"a\",\"value\":1}\r\n\n{\"id\":\"b\",\"value\":2}\r\n"
	r, e := ReadUnique(strings.NewReader(in), 100)
	if e != nil || len(r) != 2 || r[0].ID != "a" || r[1].ID != "b" {
		t.Fatalf("%v %v", r, e)
	}
}

func TestOrderAndExactID(t *testing.T) {
	in := `{"id":"b","value":1}
{"id":"a","value":2}
{"id":" a","value":3}
{"id":"b","value":4}
{"id":"A","value":5}`
	r, e := ReadUnique(strings.NewReader(in), 0)
	if e != nil || len(r) != 4 || r[0].ID != "b" || r[1].ID != "a" || r[2].ID != " a" || r[3].ID != "A" || r[0].Value != 1 {
		t.Fatalf("%v %v", r, e)
	}
}

func TestErrorsReturnNil(t *testing.T) {
	cases := map[string]string{
		"bad json":       "{\"id\":\"a\",\"value\":1}\n{bad}\n",
		"bad duplicate":  "{\"id\":\"a\",\"value\":1}\n{\"id\":\"a\",\"value\":\"x\"}\n",
		"trailing":       "{\"id\":\"a\",\"value\":1} x\n",
		"missing id":     "{\"value\":1}\n",
		"blank id":       "{\"id\":\" \\t\",\"value\":1}\n",
		"null":           "null\n",
		"spaces only":    "{\"id\":\"a\",\"value\":1}\n   \n",
		"too long":       "{\"id\":\"a\",\"value\":1}\n{\"id\":\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\",\"value\":1}\n",
		"too long blank": "{\"id\":\"a\",\"value\":1}\n" + strings.Repeat(" ", 41) + "\n",
	}
	for name, in := range cases {
		r, e := ReadUnique(strings.NewReader(in), 40)
		if e == nil || r != nil {
			t.Errorf("%s: %v %v", name, r, e)
		}
	}
}

func TestLimitExcludesCRLF(t *testing.T) {
	line := `{"id":"a","value":1}`
	if r, e := ReadUnique(strings.NewReader(line+"\r\n"), len(line)); e != nil || len(r) != 1 {
		t.Fatalf("%v %v", r, e)
	}
	if r, e := ReadUnique(strings.NewReader(line), len(line)-1); e == nil || r != nil {
		t.Fatalf("%v %v", r, e)
	}
}

func TestNegativeLimitOnEmptyStream(t *testing.T) {
	if r, e := ReadUnique(strings.NewReader(""), -1); e == nil || r != nil {
		t.Fatalf("%v %v", r, e)
	}
	if r, e := ReadUnique(strings.NewReader(""), 0); e != nil || r == nil || len(r) != 0 {
		t.Fatalf("%v %v", r, e)
	}
}

func TestLongLine(t *testing.T) {
	id := strings.Repeat("x", 200000)
	in := "{\"id\":\"" + id + "\",\"value\":7}\n"
	r, e := ReadUnique(iotest.OneByteReader(strings.NewReader(in)), 0)
	if e != nil || len(r) != 1 || r[0].ID != id {
		t.Fatalf("len=%d %v", len(r), e)
	}
	r, e = ReadUnique(strings.NewReader(in), len(in))
	if e != nil || len(r) != 1 {
		t.Fatalf("len=%d %v", len(r), e)
	}
}

func TestReadErrorPreserved(t *testing.T) {
	sentinel := errors.New("boom")
	rd := io.MultiReader(strings.NewReader("{\"id\":\"a\",\"value\":1}\n"), iotest.ErrReader(sentinel))
	r, e := ReadUnique(rd, 100)
	if !errors.Is(e, sentinel) || r != nil {
		t.Fatalf("%v %v", r, e)
	}
	r, e = ReadUnique(iotest.DataErrReader(strings.NewReader("{\"id\":\"a\",\"value\":1}")), 100)
	if e != nil || len(r) != 1 {
		t.Fatalf("%v %v", r, e)
	}
}
