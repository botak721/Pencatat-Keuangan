import sqlite3
from datetime import date, timedelta
from flask import Flask, g, redirect, render_template, render_template_string, request

app = Flask(__name__)
DB = "ojol.db"

KAT_MASUK = ["Grab", "Gojek", "Maxim", "inDrive", "Tip", "Bonus", "Lainnya"]
KAT_KELUAR = ["Bensin", "Makan", "Parkir", "Pulsa/Kuota", "Servis", "Cicilan", "Lainnya"]
JENIS_AKUN = ["Bank", "E-Wallet", "Tunai"]


def rp(n):
    return "Rp" + f"{int(n):,}".replace(",", ".")


app.jinja_env.filters["rp"] = rp


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(DB)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS akun(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT NOT NULL,
        jenis TEXT NOT NULL,
        saldo_awal INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS transaksi(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal TEXT NOT NULL,
        tipe TEXT NOT NULL,
        kategori TEXT NOT NULL,
        jumlah INTEGER NOT NULL,
        akun_id INTEGER NOT NULL,
        catatan TEXT,
        FOREIGN KEY(akun_id) REFERENCES akun(id)
    );
    """)
    db.commit()
    db.close()


PAGE = """
<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Keuangan Ojol</title>
<style>
  body{font-family:system-ui,sans-serif;max-width:640px;margin:0 auto;padding:12px;background:#f4f6f8;color:#222}
  .card{background:#fff;border-radius:12px;padding:14px;margin-bottom:12px;box-shadow:0 1px 3px #0001}
  h1{font-size:20px} h2{font-size:16px;margin:0 0 8px}
  .row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #eee}
  .row:last-child{border:0}
  .masuk{color:#0a7d33}.keluar{color:#c62828}
  input,select,button{padding:8px;margin:3px 0;width:100%;box-sizing:border-box;font-size:15px}
  button{background:#1976d2;color:#fff;border:0;border-radius:8px}
  .kecil{font-size:12px;color:#777}
  .del{width:auto;background:#999;padding:2px 8px;font-size:12px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
</style>
</head>
<body>
<h1>🏍️ Keuangan Ojol</h1>
<p><a href="/rekap">📊 Rekap mingguan / bulanan</a></p>

<div class="card">
  <h2>Hari ini ({{ hari }})</h2>
  <div class="row"><span>Pemasukan</span><b class="masuk">{{ masuk|rp }}</b></div>
  <div class="row"><span>Pengeluaran</span><b class="keluar">{{ keluar|rp }}</b></div>
  <div class="row"><span>Bersih</span><b>{{ (masuk - keluar)|rp }}</b></div>
</div>

<div class="card">
  <h2>Saldo per akun</h2>
  {% for a in akun %}
    <div class="row"><span>{{ a.nama }} <span class="kecil">({{ a.jenis }})</span></span><b>{{ a.saldo|rp }}</b></div>
  {% else %}
    <div class="kecil">Belum ada akun. Tambahkan di bawah.</div>
  {% endfor %}
  <div class="row"><b>Total</b><b>{{ total|rp }}</b></div>
</div>

<div class="card">
  <h2>Catat transaksi</h2>
  <form method="post" action="/transaksi/tambah">
    <div class="grid">
      <select name="tipe" id="tipe" onchange="gantiKategori()">
        <option value="masuk">Pemasukan</option>
        <option value="keluar">Pengeluaran</option>
      </select>
      <select name="kategori" id="kategori"></select>
    </div>
    <input type="number" name="jumlah" placeholder="Jumlah (Rp)" required min="1">
    <select name="akun_id" required>
      {% for a in akun %}<option value="{{ a.id }}">{{ a.nama }}</option>{% endfor %}
    </select>
    <input type="date" name="tanggal" value="{{ hari }}">
    <input name="catatan" placeholder="Catatan (opsional)">
    <button>Simpan</button>
  </form>
</div>

<div class="card">
  <h2>Tambah akun (bank / e-wallet)</h2>
  <form method="post" action="/akun/tambah">
    <input name="nama" placeholder="Nama, mis. BCA, GoPay, OVO, DANA" required>
    <select name="jenis">{% for j in jenis %}<option>{{ j }}</option>{% endfor %}</select>
    <input type="number" name="saldo_awal" placeholder="Saldo awal (Rp)" value="0">
    <button>Tambah akun</button>
  </form>
</div>

<div class="card">
  <h2>Transaksi terakhir</h2>
  {% for t in riwayat %}
    <div class="row">
      <span>{{ t.tanggal }} · {{ t.kategori }}<br><span class="kecil">{{ t.akun }}{% if t.catatan %} · {{ t.catatan }}{% endif %}</span></span>
      <span>
        <b class="{{ t.tipe }}">{{ '+' if t.tipe == 'masuk' else '-' }}{{ t.jumlah|rp }}</b>
        <form method="post" action="/transaksi/hapus/{{ t.id }}" style="display:inline">
          <button class="del">x</button>
        </form>
      </span>
    </div>
  {% else %}
    <div class="kecil">Belum ada transaksi.</div>
  {% endfor %}
</div>

<script>
  const kat = {masuk: {{ kat_masuk|tojson }}, keluar: {{ kat_keluar|tojson }}};
  function gantiKategori(){
    const t = document.getElementById('tipe').value;
    document.getElementById('kategori').innerHTML =
      kat[t].map(k => `<option>${k}</option>`).join('');
  }
  gantiKategori();
</script>
</body>
</html>
"""


@app.route("/lama")
def index_lama():
    db = get_db()
    hari = date.today().isoformat()

    akun = db.execute("""
        SELECT a.id, a.nama, a.jenis,
               a.saldo_awal + COALESCE(SUM(
                 CASE WHEN t.tipe='masuk' THEN t.jumlah
                      WHEN t.tipe='keluar' THEN -t.jumlah END), 0) AS saldo
        FROM akun a LEFT JOIN transaksi t ON t.akun_id = a.id
        GROUP BY a.id ORDER BY a.id
    """).fetchall()

    def total_hari(tipe):
        r = db.execute(
            "SELECT COALESCE(SUM(jumlah),0) FROM transaksi WHERE tanggal=? AND tipe=?",
            (hari, tipe)).fetchone()
        return r[0]

    riwayat = db.execute("""
        SELECT t.*, a.nama AS akun FROM transaksi t
        JOIN akun a ON a.id = t.akun_id
        ORDER BY t.tanggal DESC, t.id DESC LIMIT 20
    """).fetchall()

    return render_template_string(
        PAGE, akun=akun, total=sum(a["saldo"] for a in akun), hari=hari,
        masuk=total_hari("masuk"), keluar=total_hari("keluar"),
        riwayat=riwayat, jenis=JENIS_AKUN,
        kat_masuk=KAT_MASUK, kat_keluar=KAT_KELUAR)


@app.route("/akun/tambah", methods=["POST"])
def tambah_akun():
    db = get_db()
    db.execute("INSERT INTO akun(nama, jenis, saldo_awal) VALUES (?,?,?)",
               (request.form["nama"].strip(), request.form["jenis"],
                int(request.form.get("saldo_awal") or 0)))
    db.commit()
    return redirect("/")


@app.route("/transaksi/tambah", methods=["POST"])
def tambah_transaksi():
    db = get_db()
    f = request.form
    db.execute("""INSERT INTO transaksi(tanggal, tipe, kategori, jumlah, akun_id, catatan)
                  VALUES (?,?,?,?,?,?)""",
               (f["tanggal"] or date.today().isoformat(), f["tipe"], f["kategori"],
                int(f["jumlah"]), int(f["akun_id"]), f.get("catatan", "").strip()))
    db.commit()
    return redirect("/")


@app.route("/transaksi/hapus/<int:tid>", methods=["POST"])
def hapus_transaksi(tid):
    db = get_db()
    db.execute("DELETE FROM transaksi WHERE id=?", (tid,))
    db.commit()
    return redirect("/")

REKAP = """
<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rekap Ojol</title>
<style>
  body{font-family:system-ui,sans-serif;max-width:640px;margin:0 auto;padding:12px;background:#f4f6f8;color:#222}
  .card{background:#fff;border-radius:12px;padding:14px;margin-bottom:12px;box-shadow:0 1px 3px #0001}
  h1{font-size:20px} h2{font-size:16px;margin:0 0 8px}
  .row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #eee}
  .row:last-child{border:0}
  .masuk{color:#0a7d33}.keluar{color:#c62828}
  .tab a{display:inline-block;padding:8px 14px;border-radius:8px;background:#e3e8ee;color:#222;text-decoration:none;margin-right:6px}
  .tab a.aktif{background:#1976d2;color:#fff}
  .kecil{font-size:12px;color:#777}
</style>
</head>
<body>
<h1>📊 Rekap: {{ judul }}</h1>
<p><a href="/">← Kembali</a></p>
<div class="tab" style="margin-bottom:12px">
  <a href="/rekap?p=minggu" class="{{ 'aktif' if p == 'minggu' }}">7 hari</a>
  <a href="/rekap?p=bulan" class="{{ 'aktif' if p == 'bulan' }}">Bulan ini</a>
</div>

<div class="card">
  <h2>Ringkasan</h2>
  <div class="row"><span>Pemasukan</span><b class="masuk">{{ total_masuk|rp }}</b></div>
  <div class="row"><span>Pengeluaran</span><b class="keluar">{{ total_keluar|rp }}</b></div>
  <div class="row"><span>Bersih</span><b>{{ (total_masuk - total_keluar)|rp }}</b></div>
  <div class="row"><span>Hari ada transaksi</span><b>{{ hari_kerja }}</b></div>
  <div class="row"><span>Rata-rata bersih / hari</span><b>{{ rata|rp }}</b></div>
</div>

<div class="card">
  <h2>Pemasukan per sumber</h2>
  {% for r in masuk %}
    <div class="row"><span>{{ r.kategori }}</span><b class="masuk">{{ r.total|rp }}</b></div>
  {% else %}<div class="kecil">Belum ada data.</div>{% endfor %}
</div>

<div class="card">
  <h2>Pengeluaran per kategori</h2>
  {% for r in keluar %}
    <div class="row"><span>{{ r.kategori }}</span><b class="keluar">{{ r.total|rp }}</b></div>
  {% else %}<div class="kecil">Belum ada data.</div>{% endfor %}
</div>

<div class="card">
  <h2>Per hari</h2>
  {% for h in harian %}
    <div class="row">
      <span>{{ h.tanggal }}<br><span class="kecil">+{{ h.masuk|rp }} / -{{ h.keluar|rp }}</span></span>
      <b>{{ (h.masuk - h.keluar)|rp }}</b>
    </div>
  {% else %}<div class="kecil">Belum ada data.</div>{% endfor %}
</div>
</body>
</html>
"""


@app.route("/rekap")
def rekap():
    db = get_db()
    p = request.args.get("p", "minggu")
    hari_ini = date.today()
    if p == "bulan":
        awal, judul = hari_ini.replace(day=1), "Bulan ini"
    else:
        p, awal, judul = "minggu", hari_ini - timedelta(days=6), "7 hari terakhir"
    a, b = awal.isoformat(), hari_ini.isoformat()

    def per_kategori(tipe):
        return db.execute("""
            SELECT kategori, SUM(jumlah) AS total FROM transaksi
            WHERE tipe=? AND tanggal BETWEEN ? AND ?
            GROUP BY kategori ORDER BY total DESC""", (tipe, a, b)).fetchall()

    masuk, keluar = per_kategori("masuk"), per_kategori("keluar")
    total_masuk = sum(r["total"] for r in masuk)
    total_keluar = sum(r["total"] for r in keluar)

    harian = db.execute("""
        SELECT tanggal,
               COALESCE(SUM(CASE WHEN tipe='masuk' THEN jumlah END), 0) AS masuk,
               COALESCE(SUM(CASE WHEN tipe='keluar' THEN jumlah END), 0) AS keluar
        FROM transaksi
        WHERE tipe IN ('masuk','keluar') AND tanggal BETWEEN ? AND ?
        GROUP BY tanggal ORDER BY tanggal DESC""", (a, b)).fetchall()

    hari_kerja = len(harian)
    rata = (total_masuk - total_keluar) // hari_kerja if hari_kerja else 0

    return render_template_string(
        REKAP, p=p, judul=judul, masuk=masuk, keluar=keluar,
        total_masuk=total_masuk, total_keluar=total_keluar,
        harian=harian, hari_kerja=hari_kerja, rata=rata)

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]
NAMA = "Driver"          # ganti dengan nama lo
TARGET_HARIAN = 150000   # ganti dengan target bersih harian lo

KAT_ICON = {
    "Grab": "two_wheeler", "Gojek": "two_wheeler", "Maxim": "two_wheeler",
    "inDrive": "two_wheeler", "Tip": "volunteer_activism", "Bonus": "redeem",
    "Bensin": "local_gas_station", "Makan": "restaurant",
    "Parkir": "local_parking", "Pulsa/Kuota": "smartphone", "Servis": "build",
    "Cicilan": "request_quote", "Transfer": "swap_horiz",
    "Biaya admin": "receipt_long",
}


def ikon(k):
    return KAT_ICON.get(k, "category")


def label_hari(d):
    return f"{HARI[d.weekday()]}, {d.day} {BULAN[d.month - 1]} {d.year}"


def singkat(n):
    n = abs(int(n))
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"
    if n >= 1000:
        return f"{n // 1000}K"
    return str(n)


app.jinja_env.filters["singkat"] = singkat


def ambil_akun(db):
    return db.execute("""
        SELECT a.id, a.nama, a.jenis,
               a.saldo_awal + COALESCE(SUM(
                 CASE WHEN t.tipe IN ('masuk','transfer_masuk') THEN t.jumlah
                      WHEN t.tipe IN ('keluar','transfer_keluar') THEN -t.jumlah END), 0) AS saldo
        FROM akun a LEFT JOIN transaksi t ON t.akun_id = a.id
        GROUP BY a.id ORDER BY a.id
    """).fetchall()


@app.route("/")
def beranda():
    db = get_db()
    hari = date.today()
    h = hari.isoformat()
    akun = ambil_akun(db)

    def total_hari(tipe):
        return db.execute(
            "SELECT COALESCE(SUM(jumlah),0) FROM transaksi WHERE tanggal=? AND tipe=?",
            (h, tipe)).fetchone()[0]

    masuk, keluar = total_hari("masuk"), total_hari("keluar")
    bersih = masuk - keluar
    rows = db.execute("""
        SELECT t.*, a.nama AS akun FROM transaksi t
        JOIN akun a ON a.id = t.akun_id
        ORDER BY t.tanggal DESC, t.id DESC LIMIT 5
    """).fetchall()
    riwayat = [dict(r, ikon=ikon(r["kategori"])) for r in rows]
    return render_template(
        "beranda.html", nama=NAMA, hari_label=label_hari(hari), akun=akun,
        total=sum(a["saldo"] for a in akun), masuk=masuk, keluar=keluar,
        bersih=bersih, target=TARGET_HARIAN,
        persen=min(100, max(0, bersih * 100 // TARGET_HARIAN)),
        sisa=max(0, TARGET_HARIAN - bersih), riwayat=riwayat)


@app.route("/catat")
def catat():
    db = get_db()
    hari = date.today()
    kat = {"masuk": [[k, ikon(k)] for k in KAT_MASUK],
           "keluar": [[k, ikon(k)] for k in KAT_KELUAR]}
    return render_template(
        "catat.html", akun=ambil_akun(db), kat=kat, hari=hari.isoformat(),
        hari_label="Hari ini, " + label_hari(hari))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)