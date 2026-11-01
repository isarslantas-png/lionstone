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
pip install "lionstone[whisper] @ git+https://github.com/ismailarslantas/lionstone"
lionstone edit podcast.mp4 --language tr --title "12. Bölüm" --speaker "Ayşe Yılmaz|Kurucu"
```

Çıktılar `podcast_lionstone/` klasöründe: düzenlenmiş video, SRT/VTT altyazı, `plan.json`, `transcript.md` ve `qa.md` kalite raporu.

## 💎 Her şey ücretsiz

Lionstone eksiksiz bir editördür ve **tüm özellikler ücretsiz ve açık kaynaktır (Apache-2.0)**: lisans anahtarı, hesap, filigran, yükleme ve telemetri yok. Eski Pro ve Studio özellikleri artık çekirdeğin parçası:

- **Creative Suite**: 133 look, efekt, geçiş, hareket ve metin hazır ayarı (`lionstone fx list`, `fx preview`, `fx auto`)
- **Çoklu kamera** (`multicam`), **stil öğrenme** (`style learn`), **Reels/Shorts üretici** (`clips`), **FCPXML + EDL** (`export`)
- **Takım araçları**: marka kitleri, roller, sürümlü ve kilitli hazır ayarlar, toplu uygulama (`team`, `brand`, `preset`, `fx batch`)
- **Lionstone Styles**: `O4 W3 A3 G5 S4 P3` gibi stil kodları (`lionstone styles --open`, `--cmd O4 W3 A3`)

Hepsi için: `pip install "lionstone[all] @ git+https://github.com/ismailarslantas/lionstone"`. Ayrıntılar: [docs/PRO.md](docs/PRO.md)

## 🤝 Katkı

Özellikle kendi dilinizin dolgu sesi listeleri, yeni ücretsiz efektler ve QA kontrolleri için PR'larınızı bekliyoruz. Bkz. [CONTRIBUTING.md](CONTRIBUTING.md).

<p align="center"><sub>İzmir'de <a href="https://www.linkedin.com/in/ismailarslantas/">İsmail Arslantaş</a> tarafından geliştirildi · Lionstone size bir akşamlık kurgu kazandırdıysa bir ⭐ başkalarının da bulmasına yardım eder.</sub></p>
