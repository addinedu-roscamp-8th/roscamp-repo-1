# Order request from Main Server to FMS
string order_id
string menu_id          # M001: 햄치즈샌드위치, M002: 비건샌드위치
string table_number     # T01 ~ T08
int32 quantity
string sauce_type       # mayo, mustard, ketchup
bool voice_order
builtin_interfaces/Time created_at
