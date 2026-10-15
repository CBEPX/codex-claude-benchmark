package records

import (
 "bufio"
 "encoding/json"
 "fmt"
 "io"
 "strings"
)

type Record struct { ID string `json:"id"`; Value int `json:"value"` }

func ReadUnique(r io.Reader, maxBytes int) ([]Record, error) {
 if maxBytes <= 0 { return nil, fmt.Errorf("maxBytes must be positive") }
 capacity := int(^uint(0) >> 1)
 if maxBytes <= capacity-2 { capacity = maxBytes+2 }
 s := bufio.NewScanner(r)
 s.Buffer(make([]byte, min(4096, capacity)), capacity)
 out := []Record{}
 seen := map[string]bool{}
 line := 0
 for s.Scan() {
  line++
  b := s.Bytes()
  if len(b)>maxBytes {return nil, fmt.Errorf("line %d too long",line)}
  if strings.TrimSpace(string(b))=="" {continue}
  var rec Record
  if err:=json.Unmarshal(b,&rec);err!=nil{return nil,fmt.Errorf("line %d: %w",line,err)}
  if strings.TrimSpace(rec.ID)=="" {return nil,fmt.Errorf("line %d: empty ID",line)}
  if !seen[rec.ID] {seen[rec.ID]=true;out=append(out,rec)}
 }
 if err:=s.Err();err!=nil{return nil,fmt.Errorf("line %d: %w",line+1,err)}
 return out,nil
}
