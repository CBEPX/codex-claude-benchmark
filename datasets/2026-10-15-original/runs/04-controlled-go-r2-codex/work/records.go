package records
import ("bufio"; "encoding/json"; "io")
type Record struct { ID string `json:"id"`; Value int `json:"value"` }
func ReadUnique(r io.Reader, maxBytes int) ([]Record, error) {
 s := bufio.NewScanner(r)
 out := []Record{}
 for s.Scan() { var v Record; if err := json.Unmarshal(s.Bytes(), &v); err != nil { continue }; out = append(out, v) }
 return out, nil
}
