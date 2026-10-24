# ตัวเชื่อมข้อมูลสินค้า NextsellerAI (อ่านอย่างเดียว)

1. `.\nextseller\pull_nextseller_products.ps1` ดึง products + product_scores จากฐานข้อมูลบน Pi (ssh pi5) ลง `nextseller\data\*.csv`
2. `.venv\Scripts\python nextseller\nextseller_to_import.py` สร้าง
   - `nextseller\data\taoyong_import.csv` นำเข้าที่หน้าเทรนด์ของ TaoYongStudio (สินค้าเข้าเป็นยังไม่ยืนยัน)
   - `nextseller\data\angles.json` มุมคลิปที่แนะนำ ความเสี่ยง คะแนน ต่อสินค้า (ใช้กับแท็บวางแผนคลิปสินค้า)
ไม่เขียน ไม่ลบข้อมูลใด ๆ ในฐานข้อมูล และไม่อ่านรหัสผ่าน
