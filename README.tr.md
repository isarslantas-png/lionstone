<p align="center">
  <img src="assets/banner.svg" alt="Lionstone — açık kaynak yapay zekâ kurgu ajanı" width="100%">
</p>

<p align="center">
  <b>Ham podcast, röportaj ve konuşma kayıtlarını yayınlanabilir videoya dönüştürür — okunabilir, geri alınabilir ve doğrulanmış bir kurgu planıyla.</b><br>
  Yerel çalışır · yükleme yok · filigran yok · çevrimdışı · <a href="README.md">English</a>
</p>

---

Çoğu "yapay zekâ editörü" ya her sessizliği (cümlelerinizle birlikte) keser ya da görüntülerinizi kontrol edemediğiniz bir buluta gönderir. **Lionstone dikkatli bir insan editör gibi kurgular**: kelimeleri anlar, anlamlı duraklamaları korur, asla bir kelimenin içinden kesmez, her kesimin nedenini yazar ve **kalite kontrol dosyayı gerçekten denetlemeden "bitti" demez.**

<p align="center">
  <img src="assets/demo-terminal.svg" alt="lionstone edit çalıştırması" width="88%">
</p>

## ✨ Neler yapar?

- ✂️ **Konuşmayı anlayan kesim** — dolgu sesleri (`ııı`, `eee`, `um`, `uh`…), takılmalar (`bu bu`), tekrarlanan ifadeler ve yanlış başlangıçlar temizlenir; nefes ve dramatik duraklamalar korunur. Üç yoğunluk: `natural` · `balanced` · `dynamic`.
- 🧾 **Açıklanabilir ve geri alınabilir plan** — her karar gerekçesiyle `plan.json` dosyasında. Tek komutla herhangi bir kesimi geri getirin. Orijinal dosyalar asla değiştirilmez.
- 📝 **Metni düzenleyerek video kurgulama** — `transcript.md` içinde bir satırı silin, o cümle kesilsin; satırları taşıyın, sıralama değişsin.
- 🔊 **Yayın kalitesinde ses** — iki geçişli EBU R128 loudness (YouTube −14, podcast −16, yayın −23 LUFS), true-peak sınırı, gürültü azaltma, her birleşimde 8 ms mikro geçiş (klik yok).
- 🎨 **Renk** — otomatik pozlama, ölçülü görünümler, kendi `.cube` LUT dosyanız.
- 🔤 **Başlık, alt yazı (lower third), altyazı** — 6 ücretsiz başlık efekti, SRT/VTT/ASS altyazı; Türkçe büyük harf (`i → İ`) ve sağdan sola diller desteklenir.
- ✅ **Teslimden önce QA** — baştan sona çözümleme, ses/görüntü süresi, siyah/donmuş kare, loudness, birleşimlerde klik, kelime kesilmesi, altyazı zamanlaması, grafik çakışması. **Yapılmayan kontrol "atlandı" olarak raporlanır, asla "geçti" denmez.**
- 🤖 **Ajan uyumlu** — dahili **MCP sunucusu** ile Claude, Cursor veya herhangi bir MCP istemcisi kurguyu planlayabilir, inceleyebilir ve render alabilir.

## 🚀 Hızlı başlangıç

```bash
sudo apt install ffmpeg                   # veya: winget install ffmpeg / conda install -c conda-forge ffmpeg
pip install "lionstone[whisper] @ git+https://github.com/isarslantas-png/lionstone"
lionstone edit podcast.mp4 --language tr --title "12. Bölüm" --speaker "Ayşe Yılmaz|Kurucu"
```

Çıktılar `podcast_lionstone/` klasöründe: düzenlenmiş video, SRT/VTT altyazı, `plan.json`, `transcript.md` ve `qa.md` kalite raporu.

## 💎 Free · Pro · Studio

Ücretsiz sürüm eksiksiz bir editördür, deneme sürümü değildir.

| | **Free** | **Pro** | **Studio** |
|---|:-:|:-:|:-:|
| Konuşma odaklı kesim, metinle kurgu, geri alma | ✅ | ✅ | ✅ |
| Ses, renk, altyazı, 6 başlık efekti, QA, MCP | ✅ | ✅ | ✅ |
| **Çoklu kamera**: drift kontrollü senkron, konuşana göre kamera seçimi | | ✅ | ✅ |
| **Stil öğrenme**: 1–3 referans videodan tempo, renk, ses | | ✅ | ✅ |
| **Reels/Shorts üretici**: en iyi anlar → 9:16, yüz takibi, hook başlık, kelime vurgulu altyazı | | ✅ | ✅ |
| **6 Pro başlık efekti** | | ✅ | ✅ |
| **Proje dışa aktarma**: FCPXML (Resolve/Final Cut) + EDL (Premiere) | | ✅ | ✅ |
| **Görsel QA**: grafik/altyazı yüzü kapatıyor mu? | | ✅ | ✅ |
| Koltuk sayısı · toplu işleme · öncelikli destek | | 1 | 5+ |

Pro sizin bilgisayarınızda, çevrimdışı lisans anahtarıyla çalışır — hesap yok, yükleme yok, telemetri yok. → **[Lionstone Pro](docs/PRO.md)**

## 🤝 Katkı

Özellikle kendi dilinizin dolgu sesi listeleri, yeni ücretsiz efektler ve QA kontrolleri için PR'larınızı bekliyoruz. Bkz. [CONTRIBUTING.md](CONTRIBUTING.md).

<p align="center"><sub>İzmir'de <a href="https://www.linkedin.com/in/ismailarslantas/">İsmail Arslantaş</a> tarafından geliştirildi · Lionstone size bir akşamlık kurgu kazandırdıysa bir ⭐ başkalarının da bulmasına yardım eder.</sub></p>
