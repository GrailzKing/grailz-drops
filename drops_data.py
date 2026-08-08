"""
drops_data.py — Grailz Drops Calendar Pipeline
================================================
Scrapes all configured sources, merges with manually curated drops,
builds index.html, and writes it to disk.

Run locally:  python drops_data.py
Run on CI:    same command — GitHub Action calls this automatically.

Sources scraped:
  WEB  topps.com/release-calendar
  WEB  beckett.com TCG, non-sports, sports card calendars
  WEB  funko.com/limited-edition-calendar.html
  WEB  disneypinsblog.com
  WEB  tcgradar.eu (Pokemon TCG)
  WEB  icv2.com (Pokemon TCG products)
  WEB  creations.mattel.com/pages/launch-calendar
  WEB  supremecommunity.com
  WEB  hypebeast.com/tags/weekly-drops
  TW   @ONEPIECE_tcg_EN, @wizards_magic, @PokemonRestocks,
       @DisneyPinnacle, @OPTCGAlert, @OriginalFunko, @Topps
       (searched via Google — no API key required)
"""

import datetime, re, json, os, textwrap
from urllib.request import urlopen, Request
from urllib.error import URLError
from html.parser import HTMLParser

# ── CONFIG ────────────────────────────────────────────────────────────────
MONTH       = datetime.date.today().strftime("%B %Y")   # e.g. "August 2026"
MONTH_NUM   = datetime.date.today().month               # 8
YEAR        = datetime.date.today().year                # 2026
OUTPUT_FILE = "index.html"

# ── LOGO (base64 embedded — no external hosting needed) ───────────────────
LOGO_64  = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAeBUlEQVR42m2aaYxlWVLf/xHn3OWtmflyrcyqrH3t6uptppeZbmZpBoYBBjzYNMNiG5ANwtiybMs2loU32R+Qlw+2kLDBtmAksJDFZmBoYPbpfauu7qqufcmlcs+3v3fvPSfCH+59WdkepzKfnl7ed29EnIg4cSJ+xBwCBEDxnT8EKBFr/m+i/A8AiAFVBQAiArGqEjEIOroaRKO7EgGqSgQQqwpU8i+qKlSL6/dEyO+L0WvxaN33r30iMkffIT3tf0+0Xz3a+wSgXEFQoWquIUDERiG5fjTSZiRa8YVCe5XcJqOPHkhJhEI9wodF1/1q2H2SFWYoHkYASEfGIDCIoZrbG6oKIuK9JSmWhRgAsQEA9bmRMRInv2NxexFAlXjP1porUlwPxT7DQ/busM92Cqj9DsM/EEihRIyRPgQCcWFvYh7ZO781scWDCxgEsCUowJSvBoEIokIgVVEuPsjtpiqFJjwSdM/2ADS3lEDz5dy3AiMPK4RU7Dlt/sd7njPydx4tOhOxEgEMgE2A/JNcMA6FPEFBrOpJIeoBIaiqAkJqAIUKFHlIAFrYNTd2LhXtxcOei+aOpiMFHoheKE5k9sR9ELvEKHyBqTC8YTYAEVkFE1kiS2zAFmRBLLl5SYlZRQyJqoM4qIM6FQEEAMRBfa5a7keqCtLCqVUeiK6yz9OLD+0+Bxqt/sihi+AiQ8XCMRERmZG/W8AQWWLLHIEsOISJQZGxJdgSOKQgUIaH85qp9CXrqh+ITyEpNIM4VQ9meEck6h0A3bMkFJA83kbhzg/CoHivtvAKaJ4O98KNikxo9nk85yFBsESGyDIFzCUyEShmO1YJD06UFuNgjEuht14tUk5dKN4gZcqMDmWQDHfS1ppvb1LaVt8neBVHPlWfETHUQ1XFf8hvIYACplAJe7Ge52KOmUzugLznOSACFSoR504NIoIhGEMBUcQcB1wBVeJwdi46Nx0fJvat9O6Wu9VM7w2SrdR3vKaAEhsTlEypbuuzdmJB6zNJWE47237rNgY76jOkPU178Am8UxB8lqdXIlIViDxINOKLgFGB+jzjlWnPbfa5eGHswuRMxARmCpmMoVJAlcA0DKaPVJ48EB5sZbeWeq+sDN7r+V2FAxGRUYJSnslF4aEK8SAOoko4uWgOnte5U0ma+pUraK0hbeuwA5+peoh/IGieeXQUx4UOChWIz61TGW1FVPh9EQEGxAADyhg5DIKAqyUeZ0zMho88WnlmmN1/q/0HK+llp6nhkA07zTxlAhF4US8otiowqbFgowBUGQjGZqKTH5djjw3Xbsu1N2i4AzeUbAifQTKIQByIIB6KkfPsKZC/qiEOCUSjPENEBM4dhgur524TWopCqsbciGTxmfoPPlN/9Erzy681/zDVQcnWCUbJeU0Fmaovfgv3VZCOdlAlYgpLVBoX5Wzttm1tVE58xM8dc81tFgcQQXL3BQA2xa7y/6sSFDB5KZF7Du/FMTGTgeZvAsuRpTimsRJPj/kzX1j48QMl/bO139lINup2UgmpdjxSgffqlIoUUCRFqBYxxcgfwobyLTaq8cS8z8TfvVKfPmRPPzlod9gledooKpFiUxew+dCuX2igxpg4lzvfxRhsKFeaDFmmwFJoUYqoXuLZA/6Jnzn/EwO99c27L5VpJuKgLzuJdkTVIfVwQo6ggkyQqTrAFzkk3+6IwQYmJBuRjRlCxvLYAarNpOtLtUqp+rHPdFsDHnSLHE4GtFcjCjGP0ivlRQ0RGcPxXhHBlDuSFtLDEoxBOeaxEs0s6Ef+1lMvLPXfXF9un6482pLtHb8qUJBJMfCUOCSCzCNTFSmKTNXRbpIvQv5UGAsbIygTAkvKtUZw6GwqWdVi/MmPtVoZe5fvhjBB7taWbV6PgAgqqsrEpDCG48L1iRh55ZO7vjUILZVDrVV4ZiZ75Bee/qnbw1dtNz43+fj97G473Q606uATdBwGqfQ8OYWMShNVCPI8OKpLQAQ2ZGzusRRVKB43QdUw8fh49NAFsSi7dPqpJ1u7mQUTGzIRKFCylagmgKiH5nlJAVX1xnKpCKwigYIpiGwJygGVI62WaKyaHfvpcz/VNNemSrWnDz11o311OBgEaSNFOjTtoXQS3xdSwIs6hQOJIMtrnr1KmpiImYjBgZqAbMxsgqjMtWlbGTcGwUxj4ulHOJao3Z9+9JFNtensrEwd1MZiWJtNJfCZUiG9EBQqTMYwRXmOB/K0YxmGYCxKASoRVQM38wOzL4wf6N+9sfSp+Y/flBug/lx2pIv+tizDwUGVxWHgZOiQyl5pNrK6EoMZxMQWbNmGRAYmpNKELU0ElThYmMPsbNgIwwPjcvjgxuU70+XoIz/5zNmnji8+/VD5oZOd46eHh06FUtZmh9SrplAHEVE1xpT20miRNMmQWoMoolqExln77HOnz/7ZlRcfD59ZGa51su0TpZNSTzb7q9QrO1W23Ne2iChIimwtRQLNq6g8sRkLYykswwQcVzgsmUrNVGp2bNJUTfTshfDc0eHyWndtwLWJnTevnj4+vz1VsRbnTzQ++ehcfbFxo7bAaUk21lgySEriATGW41EpSwzDYIIJuWJRilAdy479tWNfeKXzJ+lOhACr7o7tjg181gk25tOD1lVTM+j5pvWRhxfKlJxHWiRNMiADZiUmNmAmNmxCCkoa10x9xpQrZmKcFg8GJ45GJXgTDVa6dGfFDSntDu6/frnjGm//2fsXL65e7ybf//DMs6cbr7m63NzQ3RW4nvpExRdZiMBEhsAMC9gApRDVUCeeLn26OjV48faLU+GBJX/dZdTPsqbZnBjOHK7Nmch1k15pWMsk7VMr0YEnIQqsicEsRRyD2JCNKCjBRgoiG9uoYqvj4dxi2Bizxxfs+aNJJ01eft+v9/3mjr+/AjGDax8crNW7q+v61uvJnd5fDuwPPDYTzlYuv7nOK3c03YVPoGKsKQNgMoRRrQbLCEs0NqnHn5/7zJd3v7Tb7w65PZBO4tPM9pGB+zHYJ3HnxPAYeezQZiLOmnJEcYphX5uJ72R+WOwG4qCOVCkocXWSymNcrgTT0zw3p6ePVBtlbfV7t7fc6pasrblWT5obvrvtUufWbsdHz+1eeYN3liSrNk8vPHV47NtXW/bWmvbX4Xok3mp+zB2dSUEwsAEi1uhkdKHtl67svjtu5nb8SkwVTzrIdvtJ39io2br/WPOJ8oS1teHkyrQx9XUsXXZXd2Q51cSJQ14V5/W9MgHoJgwfTc+bA4epGkczFRyb67WGcumqrDVda0jNDZ+SZin5NqLq7vr2wpkn7PRhv/S2Ll93zediAzowSTPzukxgCyJLRACpaB7IBtZQFGgp1LFD9sgrnd9NdDhEhwhDHQzRI0cBx3f9tSP9I1vU3OwvT0Vj52pn3+m/9W7vqz1tEthSqVGbr9UWUBp3LKnb7vRXu601kGrSHt56o35kMXrkIQqh1++lTZG1pm6sa2dAyZCznnOeZCBZT9K0f/WtysKF7toNVOoLY6W+V0mcGY8LcwOWHnRPOHchUmYEM3wkYHmv97ohO9AWxBAxA6FWWrIRUamj0xfpzVqzXi3Nd0vrX0l/P8EA4NnS8eOTH0nDsOXbfWRKKFfLEwePiZXlO+/2tu+ySu+VFyceOd0JJ7L3rlI31XaPWjvcT7zPkHZUUlWABGS7Sx9Ujz85nDku584+fGT89Y0e9zMhB58Boqq2aDeRISISIpDhQMXM2cUtub0jG1VMZpp4lRCRwBp1XW0qYZvXRTXk8aV07S87X+pyv2zGDlfOHaifuNG72Wy3PMMbeEOup9ry8XjtyIXn1pfndpbekzS5/6X/Wf34X0GzK5v31ZH0+zrsep+Qz6BpUYJbO+wPx9OuOf/Rx7774cMV+19f34nTxO9sQH1eQORnYiYwhJiY1VgNYqo1aOZG8hepJhmGnjIlTaGQ/FymmQ47uhujCvVX3EubuG8kOFN7fLF84vWtN1N2gY2NsZkFByBLYvywn6xeuTJz/ry31Lx9KdlctW+/bMYWXNLxaeqzAfmeqhc3JIKCwJbZStjgzNSff/xnn578SsftXt6aHja37twDK5wAYCIyzKOGGzMZgCs0VuLSslxRqKPEaSIqecGcap9AIUfGcGTjoems6r0aTc9Hx89Uz9xofVDmcpnqgcaW4sCWjCmzCWEiW65qVFq/ca1x/FwwPkdRKWktk+9SwMSOAwgJ1IOh4vK2kto4bpxIzjz0tz8xtW3N77+2ejAZ+ps3fGsTkuRHdzvq4xEJM5m8Ao1RS7SzKUsMdpoqhIlEyRBIyVJkXGTSeglTXWQeYdlWH9Znt5ccfCOyxPUERsSEPVc2gddoqJx14U1Je8NuuNOcOH1h/WI7I2oO2ihXkQ7hBcawOkh+oLIa1uLKEXrs+U+/8NCZOv7pre74B8s27e1+cJOlpZJBBRCbd/vyJJp/1cBGKDdlq6dNhhU4Aue5MIANudTwc89Pfv7JT50fq9Qc5PryvaVLuz/42eeGNlHG5lL65VffXjF3wtkTn/uJR69u7Lz1tVdoLH3k+x6/t7F1arZ+/eV3YktUn548d+Ljn/8sB5Hv9da7/Usvfm3w1hsEUg01GK/UH0ouPP/8Lzz19GH7K3ez/qXVYJiuvX9b12/A9SBp3hSzxSlH85NAHtAacdTR7RSJhVWVvJNkyFqysVaerHzyX/3u3+y0s63rfRtakfDMXPyJf7Nw548TU+LDzwdj/7b2q79Jn/1Hz/3i3597b4if3uqs6tYv//zz//7iyt99fOFntppye8WMNWpHDn/umce2jR2bqP18JbjQH1y+eAkkFM7Ozj+3feihz/yDJ58/Gf3ON9ra7afXN4d3V7O3XkW6q7n/qALIN3wAYOSbMUHJwiTaF/VFI2CvF0fGuODU0eNc1l/9/Nfvvryz/n5r+f1tU6GdV/03/sXG1/7xVvuWzp8tLU6cfeFHZ/71i6372+6HfuTcsDbpsjSthEnig8CIojw+cfvLf/lzv/Sffve9W4cZ//Ldm7deu4iwEoyfWjz6ue6xx1/4paeeP135zf+zzq8vDa5v63ozff1ldFfhh8W5Pk9UNCoWATFkGMYgNIgG2AGxocCp+1DfBcQg8VBkaTqcOjr5Yz/5xLu/1h57lj7/Gwvjj/NwIF//qfanvjA/u8Dn21Gjzj/+selfu3lAM1E2xtDW2Fg6NYPuZnTq5C/9k599/Pihf/anr7z723+Cu5sTix+dmnp6Z2byi79wemE8+tJvrdCV27evXZt87qPpjavY2VDXJ3UgUiZ4gMhYUyFlJmMRGgQBynWaWuSHMh3c0YsWkUJyBYjYIopMPN6b+76ffOrUd82xmMmFupC072VVG//HH36p9S4ufP/42rfpe/954/KNZPV692oreeR4tTlZOTFZevX27scny89eOPzUE6eeePr89LNP/edHjv12a7Bg+TOfeHSjfoLcKXr44M/9w3PSxR//+i26eOX22y9V4lqPtX3vGpr3Neuo66ukBIV6eGesKROxQWA0DFCKud6Qw0+UPlE3pXfSbwUUKokWJyo2sIZtd9hZe9HFUYlJV9bW//d/+8qNq0vuevCNtT+/eeOe3JwIa+b6xe6Xfv2d3/vTV1569falDu02+69f37nx1Xe+cnk5YO677P6du2++eekvtjv9Vl+ialiZvdufmDkz/mNfPHj7rf6l31rKrrx99dJfEEln+5pMzrndFXS31PWQ9Umdjs6WFNspQ4HVOEKtRGNTeuTx+Pm/Ovv5/tzyL776dxK0U7RFfd5nDxAHiOo8Xs0aRkvjmM6Q7NB9IX4k/AhH/r6/H/QnydS7LMOxXlIeulLUsSUXmIySIEj6MpSFBWcHg4vfRhjQgbMzRy+U64fd3Nz3/MDsQ0fKb/5e69YfXF2/99rq0rfBnKTb1iJ69ouD669h6xaGOzpswqejBp6zBCZYg9AijnX80drTz9Az5767Kp9bmPrC4jpdFcQeGYEUnohU/UB6URin3A8JY9zY9klH2++Yl58JnvXO9StLQjYxmmZwPXWZNWFAhgJLXmSsXJqLytcvvS0STY6feezU53RhofLY+BPP1vqb9OZ/2Lj3jXcuL3092f0gDKJh1tL+upk8qKWYxCmcqhRDCV90di2BWY2h0Go0y8fOhI+fOtyY+xvm1v+ojlFjjTTQKJ87CYhBlsK87LZiHbIylWcxvylrCdKLw7cerj52uft+V7sixjM5sMCKZGSMgEtxbWH2zM133zf9+oWDnz72yDPxozMLn4rnD0V3vuWW/9e9Sy+9eKv3foA0Ko/3m9cy6cMltj4hpUhdBi+kfjQghIqoihUVIma1AdVPRY8ei+ce/rnx1a8m3/rvnahUzob9CtVAAqgoW9gIkaXAKDdoQplKGp4rfcylyeX03ZvpZUfpmfrjy8P7G8l6BvUwRMTC1kRT4wuN2cW7d+5PJkdPzj994JkjJ3+0PvOYvbusH/yX1saL195c+mYr2q0EPBg0k+6Spk2KapQNeeZQ1mpi0FI/hEtJPamIFM0VO5qCcY1mZrC4eLZhxsyf//LNb5q3rZSUhAAGWwRKQuAyVWMqBQinzXSVamFUnm0sfhf98J2l5aasXh+8t56un6w9sVg9nZJ4smxLUVgJw6pSWZfip8JPzD9+dP4LleM/FDYZH/x5lnytvfrKu+8PP/DzbO8nvfadJN02LnUmAhkbBJhY9Mt3KenBJVAP9aqaj5QAtUyWlAl2Qg9MBo3ykdK9byWvrVy7Gr4+g7mymRLpV1ABEFAk0IiiBk3GXKpy40TplGv4q7LWFl4cfzrZ/eqA2h3Zeqv54kRwcDw4VA3mWMxwYDktnw1OPnru5MEXKrNfpOY4Lr4szW8murS9srW0dWRgt8LurXvJ9m1iH1CZ2UtYh+9Hs0eVK7p+i10CybvFePBGMSrmYAxK9bjKddq6Nlyl1W29W/HxnD2xqm/VeaIv3RpqMZXANEYTDZ4y5bIeHUdiltffXEpWMu1NxUfb6UbiBwTjvG9KczgsH86OPFf96PPPnjzy2Urpc7ozKe++IUsvYXBza1M2ezO2fcjItW2+tRMIx5WJgY8Dv+NNSHGDdzejw9/d296i7o66gboUKipSDIDzEZPCK0TUD7mXpOgnGZPx6hzSbVma0IV1U4FKg6cINMOzzDawlenx41yJb/Tu7fbcUKFIh8Nt75IqGjNcHQ+mJv2RuH/okejkJ549euqFUunTrge38i1cfY1W7nWubly5nK3Ec2OxiYWas6Zh52PZvqkQ+Ex92udxzy6sTaF6wt96jV1ffALJIBkpNJdeNR90i6hXcrtYvZ/e37o3ceTh+pN/9OgqXWm5ezWePhif72S3j4enBm6gEh6snfEVsZOB82F/1a33bw+zfuDNAT7SiKuzND/vT4yn81OV6dOfHjv9I2F4wXVWk/XfoI2rfL25+Xb3yju7dzZ0x4SKG760Yg6dOF+bm8r6Kz6ZKJtGp3+vh9moPo31V8aPfXJ3c4N27qnrkmTF7KzIQqxQiNg8wTsku371qr9y6tsnT36P/+T3P+z+xL9d+kbLbY/JYSlhoNFi/awLU66MNcYmlnbup71OkJmz0Rkb6qSfms5mZzA7OVGrnwxmPxbMPxWI+J2LSecP7fZSdnO48ebgg/dbd7b8btes9nVTuxJHExSeaq63TUSlCLWZE/20tb7SiidPbiXXa43DLj6WXX9RXVvTPpGysZJlKh4qCiFVJbICJRKviVDng+S1w+7c1G+cO//3yp+ZvXDqm0durtxpJS2eurCN1fm5UxNRebffqqXjZ7jhWMbKtbKWK6VyedZMHrOzD9vqIlum3i1/57fS9hVa2dq9ybdvycp6u9uSzibd3NArvcE2EcfxpKDa725t+yyTsaOHz1Xny7zVrp188h51O++9OnHoueu3LtFwg7I+xIM81BMUTPnsOM9CFNtpA2tRDrQyzouzuPAwffrC3NFn/vp0eTFoLmeDFd/eTBOTpombnazF1mR9CctBadoEk1Sf5VKdmXm4QjvvuK1308Gq6yaDbbuzRMu3u8u9rKdwG3T7rn+n6VcBZQ7YRNbW43AqpGoUTxycvjC/eKg2ntaDue5Y5Y3X/2i8tnh5ab219nWfrotrqw4FDiqqAvU575K/WkAF3iNhmK5sKl1xGKzfP3fp3504c/jQsUfq40eCxZPVqMZBmYOY4sgQadqRrEXapNZL/u694crV7vpKbyfbTUrNdtTqodfptrNsmNn2Gm4tuctd2QYJKI9AUVHNlDSDnSzJVH/YXl++XnZn7NmpS2/84XztwNIud9ffQbarMlA4qORkzigL6QOEJ7INgA2sQRhorUQTU3yyRtMByjWZj7LqGI81qhONam1+aszU3WDbj5tKv5f12/2+77TcVtt3ByottPu028bu0CcOiVB3R5Z2ZDVBH+RVxZNoMf1lQ5E1keFqOToUBxOBKR2auDC/+NDN7ZemJxvbvYnL174u2Y0s2/HSUU0BUXUiDhAVrwWRIFBvFUpQgSf4DF2obIsSaY0PdM0yhfU2tT3tZG4i22pMDMZapc13VldmzEzCadNvdbDT0p1d7PQ16/qdhFpDaQ6wm+hQIYB4iKrPjZdvOARSdV4DAzjfTOFjczIVefm935manN9uTnxw6yXyy951VYZQEfFEmk96VHLiCFCfYxN5b1RVRciBNNN+H7qqPeOuNewhi6PkuIKyS5NOthMMXSWOE/Jf7/4pK3rSbvr1njYT9DMMMwydDBUiEFVVElWnKKgZxchwECYFxEvPeROZRuKb1za/vDD9hPojV69/TXXJubZIX5CJZvm8U5GP7PMps+xBKxTaCRTjK5Obx1AYIDYaANZoaCiMUI5RjVGKKa7L+ERw4A7fvJ69HIAilFMM+tp2mihE4L16pWKbzMf0exAAVPMpE8EwB9aMBabu/DCKxo/Pfm/mJ5Zbb6Tunsvaon2FEx2qOIWoOlVR9URQ8VSooVChwIxRwbdRfq4HyFBgNGBYJmPIEoxVaxHGVClRpYbGFB3umP4V/1LLLxsFwA5ZrkM+ntnbKgtyrOiA54NKSxSagtWj2fEnFqof3+7vbiVXnN9wvi/a9zIE8kGbh3oUAJsAqvmJfgQRUWDGco4tHzERqJhgwlAxmM4PPcaqtRxFKIcUx6hM4GDZTG7y/TvurZa7B3UMAxgAAr+3AqPxDxNMPuhTQMkzeCw6vlD/roqdX+9f30mvOumIDr2mCqeaqXpAc9sX434tbrs39IcqGVMrUJrRwVdUSXOyL5+aFXwWwxoKGMYiDKliNQypMsWLoanvYmPdX931dxNpqbi8tQniffTaaHpPNrYTY+Gxqfjhip3rZFu72c2h7DjpOx2IZrnDQAUMAnmfEJE+KD9lH75YKFDlAkmhPV4yZyhHY2PNeRyCGQ1yrCEbaASyluKSVqs0VTWTGbI+mh1sd/12UkSFL7oBFMamUTUz5eBAyOMWtqO7bb828FtOh14Sj0wkAUnu2szwzoFUxYMKuFH3TYgfjEKNqY4muQUhR8TFvKNoB9HoAiYg96h8lE+wDMtqDQWWSiWuVnQsoKoSCwmUKZ/wERFxYGIP3/PtrmwN0UykL5p5ylQyJa/qJY/UEVaT5/c86++jLfX/IVcKBRT7WMsCPMv5S87x1ALJyZkQmILOyYEQsCELGBBZBMhpC7UG1lBIxB5eCR6ph/NwHqLkvaYiWV4H5NvzaDgLFZe7cx4GRJzvvgRoTjnudyHm8ohqesBj7oMVc9WIizlaAepqQSeY0Xfy6NS8M8kcEIiItIAlczpDRYWZBV4gI2OLqCCv8CF5lswhFRH3AFD8Tvx1VNDZEVyq+oBoHAGERCMilQXKIMlZ0nx9NYcaR2xp8SwFMWlGBempoAIZzH3DCeEBgpXzDiMuMa+R8j6zMeLTBymA8CFoS/fFAHPpQ1D0iMwYUa976zKiMJHjQEp74UFEICnoXspbN1DSYoPkXERF8X4PEN7bVkegoe51wvdnrw+ZPDfuHmcKGMDQPk563zdp5HaFw+t33LSAp4n2CO59GLnmRYTC70umeZIRpREMh32JBfuzLuXEHY3w0cKRdA9c1FHEcrRn9f209z64a4/OphGMPuq604Po1w8/fhRTRVFReKPuAbhQ1WKdQQV3XAC7+BDPrh9eDZUPM1tqiOyDJR0FQb4YBTCPD8PwBZVND6q0gjof0dqj6TYgqkIPAO4H6PqDW+keHjoCQrE3sZDRen4neP9Aq/8LoTXLnDf9xqoAAAAASUVORK5CYII="
LOGO_FAV = "data:image/png;base64,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"


UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")

# ── CATEGORY COLORS (matches Excel) ───────────────────────────────────────
CAT_COLORS = {
    "MATTEL CREATIONS":   ("#6b2d8b", "#fff"),
    "TOPPS":              ("#1a4a6b", "#fff"),
    "POKEMON TCG":        ("#b8860b", "#1a1a2e"),
    "MTG":                ("#0e4e2a", "#fff"),
    "FUNKO POP":          ("#4e2a0e", "#fff"),
    "ONE PIECE TCG":      ("#8b1a4a", "#fff"),
    "PANINI":             ("#0e2a4e", "#fff"),
    "VINYL & MUSIC":      ("#2a0e4e", "#fff"),
    "SUPREME FW26":       ("#8b0000", "#fff"),
    "COLLAB / LIFESTYLE": ("#2a4e0e", "#fff"),
    "DISNEY PARKS PINS":  ("#00457c", "#fff"),
    "MOVIES":             ("#8b1a1a", "#fff"),
    "DISNEY LORCANA":     ("#1a3a6b", "#fff"),
    "YU-GI-OH!":          ("#6b1a1a", "#fff"),
    "NON-SPORTS CARDS":   ("#3a3a1a", "#fff"),
}

def cat_slug(cat):
    return re.sub(r"[^a-z0-9]+", "-", cat.lower()).strip("-")

# ── FETCH HELPER ──────────────────────────────────────────────────────────
def fetch(url, timeout=10):
    try:
        req = Request(url, headers={"User-Agent": UA})
        with urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] fetch failed for {url}: {e}")
        return ""

# ── SCRAPERS ──────────────────────────────────────────────────────────────

def scrape_topps():
    """Pull drop names + dates from topps.com/release-calendar."""
    print("Scraping topps.com/release-calendar …")
    html = fetch("https://www.topps.com/release-calendar")
    drops = []
    # Topps renders JS — grab what we can from the raw HTML text
    # Pattern: "Month, Day YYYY" near a product title
    month_abbr = {
        "Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
        "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12
    }
    for m in re.finditer(
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+(\d{1,2})[\s,]+(\d{4})',
        html, re.I
    ):
        mon_str, day, yr = m.group(1)[:3].capitalize(), int(m.group(2)), int(m.group(3))
        if mon_str not in month_abbr or yr != YEAR or month_abbr[mon_str] != MONTH_NUM:
            continue
        # Grab text nearby for title (rough heuristic)
        start = max(0, m.start() - 200)
        chunk = html[start:m.start()]
        title_m = re.search(r'>(2\d{3}[^<]{5,80})<', chunk)
        if title_m:
            name = title_m.group(1).strip()
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:70]
            drops.append({
                "cat": "TOPPS",
                "date": f"{MONTH_NUM}-{day}",
                "name": slug,
                "url1": "https://www.topps.com/release-calendar",
                "url2": "",
            })
    print(f"  → {len(drops)} Topps drops found")
    return drops


def scrape_beckett_tcg():
    """Grab TCG release names from Beckett."""
    print("Scraping Beckett TCG calendar …")
    url = "https://www.beckett.com/news/2026-tcg-release-dates-checklists-and-set-information/"
    html = fetch(url)
    drops = []
    cat_map = {
        "pokemon": "POKEMON TCG",
        "one piece": "ONE PIECE TCG",
        "magic": "MTG",
        "yu-gi-oh": "YU-GI-OH!",
        "lorcana": "DISNEY LORCANA",
    }
    # Look for month headers + product lines
    month_name = datetime.date(YEAR, MONTH_NUM, 1).strftime("%B")
    in_month = False
    for line in html.splitlines():
        clean = re.sub(r"<[^>]+>", "", line).strip()
        if month_name in clean and str(YEAR) in clean:
            in_month = True
        elif re.match(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}", clean):
            if in_month:
                break  # past our month
        if not in_month:
            continue
        if len(clean) < 8 or clean.startswith("http"):
            continue
        for keyword, cat in cat_map.items():
            if keyword in clean.lower() and len(clean) < 120:
                slug = re.sub(r"[^a-z0-9]+", "-", clean.lower()).strip("-")[:70]
                drops.append({
                    "cat": cat,
                    "date": f"{MONTH_NUM}-TBD",
                    "name": slug,
                    "url1": url,
                    "url2": "",
                })
                break
    print(f"  → {len(drops)} Beckett TCG drops found")
    return drops


def scrape_beckett_nonsports():
    """Grab non-sports release names from Beckett."""
    print("Scraping Beckett Non-Sports calendar …")
    url = "https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/"
    html = fetch(url)
    drops = []
    month_name = datetime.date(YEAR, MONTH_NUM, 1).strftime("%B")
    in_month = False
    for line in html.splitlines():
        clean = re.sub(r"<[^>]+>", "", line).strip()
        if month_name in clean and str(YEAR) in clean:
            in_month = True
        elif re.match(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}", clean):
            if in_month:
                break
        if not in_month or len(clean) < 8 or clean.startswith("http"):
            continue
        if any(kw in clean.lower() for kw in ["topps","upper deck","panini","leaf","rittenhouse"]) and len(clean) < 120:
            slug = re.sub(r"[^a-z0-9]+", "-", clean.lower()).strip("-")[:70]
            drops.append({
                "cat": "NON-SPORTS CARDS",
                "date": f"{MONTH_NUM}-TBD",
                "name": slug,
                "url1": url,
                "url2": "",
            })
    print(f"  → {len(drops)} Beckett Non-Sports drops found")
    return drops


def search_twitter(account, keywords):
    """Search Google for recent tweets from an account matching keywords."""
    query = f"site:x.com {account} " + " OR ".join(f'"{k}"' for k in keywords)
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}&num=5"
    html = fetch(url)
    results = []
    for m in re.finditer(r'<a href="(https://x\.com/[^"]+)"', html):
        tweet_url = m.group(1)
        # Grab surrounding text
        start = m.start()
        chunk = re.sub(r"<[^>]+>", " ", html[start:start+300]).strip()
        if any(k.lower() in chunk.lower() for k in keywords):
            results.append((tweet_url, chunk[:140]))
    return results[:3]


def scrape_social():
    """Lightweight Google-based social scrape for confirmed dates."""
    print("Searching social accounts …")
    month_name = datetime.date(YEAR, MONTH_NUM, 1).strftime("%B")
    drops = []

    tasks = [
        ("@ONEPIECE_tcg_EN", "ONE PIECE TCG",
         ["release", month_name, str(YEAR), "booster"]),
        ("@wizards_magic", "MTG",
         ["release", month_name, str(YEAR), "prerelease"]),
        ("@PokemonRestocks", "POKEMON TCG",
         ["releasing", month_name, str(YEAR), "tin"]),
        ("@DisneyPinsBlog", "DISNEY PARKS PINS",
         ["pin", "limited edition", month_name, str(YEAR)]),
        ("@DisneyPinnacle", "DISNEY PARKS PINS",
         ["D23", "release", month_name, str(YEAR)]),
        ("@OPTCGAlert", "ONE PIECE TCG",
         ["release", month_name, str(YEAR), "promo"]),
        ("@OriginalFunko", "FUNKO POP",
         ["releasing", month_name, str(YEAR), "exclusive"]),
        ("@Topps", "TOPPS",
         ["releasing", month_name, str(YEAR)]),
    ]

    for account, cat, keywords in tasks:
        results = search_twitter(account, keywords)
        for tweet_url, text in results:
            # Try to extract a day number
            day_m = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', text)
            day = day_m.group(1) if day_m else "TBD"
            slug = re.sub(r"[^a-z0-9]+", "-",
                          text.lower()[:60]).strip("-")
            drops.append({
                "cat": cat,
                "date": f"{MONTH_NUM}-{day}",
                "name": slug,
                "url1": tweet_url,
                "url2": "",
                "_social": True,
            })

    print(f"  → {len(drops)} social drops found")
    return drops


# ── MANUAL / CURATED DROPS ────────────────────────────────────────────────
# These are the high-confidence drops curated in previous sessions.
# Update this list each month — scrapers will ADD to it, not replace it.

MANUAL_DROPS = [
    # FUNKO POP
    ("FUNKO POP","8-3","funko-pop-archangel-x-men","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html", "11:00"),
    ("FUNKO POP","8-3","funko-pop-psylocke-x-men","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html", "11:00"),
    ("FUNKO POP","8-3","funko-pop-sabretooth-x-men","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html", "11:00"),
    ("FUNKO POP","8-3","funko-pop-bishop-x-men","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html", "11:00"),
    ("FUNKO POP","8-3","funko-pop-mega-man-x-capcom","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html", "11:00"),
    ("FUNKO POP","8-TBD","funko-pop-mystery-warner-bros-horror-icons-blind-box-retail","https://funko.com/new-featured/coming-soon/","https://sdccblog.com/2026/07/funko-san-diego-comic-con-2026-exclusives/", "11:00"),
    ("FUNKO POP","8-TBD","funko-pop-chainsaw-man-movie-reze-arc-exclusive","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html", "11:00"),
    ("FUNKO POP","8-TBD","funko-pop-monsters-inc-25th-anniversary-set","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html", "11:00"),
    ("FUNKO POP","8-TBD","funko-pop-over-the-garden-wall-series","https://funko.com/new-featured/coming-soon/","https://funko.com/limited-edition-calendar.html", "11:00"),
    ("FUNKO POP","8-TBD","funko-pop-august-hot-topic-exclusive","https://funko.com/limited-edition-calendar.html","", "11:00"),
    ("FUNKO POP","8-TBD","funko-pop-august-entertainment-earth-exclusive","https://funko.com/limited-edition-calendar.html","", "11:00"),
    ("FUNKO POP","8-TBD","funko-pop-august-fan-rewards-exclusive","https://funko.com/limited-edition-calendar.html","", "11:00"),
    # POKEMON TCG
    ("POKEMON TCG","8-7","first-partner-collection-series-3-hoenn-kalos-paldea","https://icv2.com/articles/news/view/61079/pokemon-tcg-2026-product-calendar","https://tcgradar.eu/guides/pokemon-tcg-set-release-calendar-2026", "09:00"),
    ("POKEMON TCG","8-28","pokemon-tcg-mega-dragonite-ex-tin","https://tcgradar.eu/guides/pokemon-tcg-set-release-calendar-2026","https://x.com/PokemonRestocks/status/2065098551382655149", "09:00"),
    ("POKEMON TCG","8-28","pokemon-tcg-mega-darkrai-ex-tin","https://tcgradar.eu/guides/pokemon-tcg-set-release-calendar-2026","https://x.com/PokemonRestocks/status/2065098551382655149", "09:00"),
    ("POKEMON TCG","8-28","pokemon-tcg-mega-zeraora-ex-tin","https://tcgradar.eu/guides/pokemon-tcg-set-release-calendar-2026","https://x.com/PokemonRestocks/status/2065098551382655149", "09:00"),
    ("POKEMON TCG","8-TBD","pokemon-tcg-storm-emerald-mega-rayquaza-ex-english-preview","https://tcgradar.eu/guides/pokemon-tcg-set-release-calendar-2026","https://www.cardrake.com/guides/upcoming-sets", "09:00"),
    # Pokémon Center Legendary Moments Monthly Pin — 2nd Thursday of every month, 9:00 AM ET
    ("POKEMON TCG","8-13","pokemon-center-legendary-moments-cosmoem-monthly-pin","https://www.pokemon.com/us/news/go-legendary-with-pokemon-centers-2026-monthly-pins","https://www.pokemoncenter.com", "09:00"),
    # ONE PIECE TCG
    ("ONE PIECE TCG","8-3","one-piece-round1-arcade-exclusive-promo-pack-phase-3-entry","https://x.com/OPTCGAlert/status/2083597291852607623","", "00:00"),
    ("ONE PIECE TCG","8-28","one-piece-tcg-op-17-the-worlds-strongest-warriors-global-simultaneous","https://en.onepiece-cardgame.com/products/","https://x.com/ONEPIECE_tcg_EN/status/2075989349028508136", "00:00"),
    ("ONE PIECE TCG","8-TBD","one-piece-tcg-eb-05-heroines-edition-vol-2","https://x.com/ONEPIECE_tcg_EN/status/2067925359555690647","", "00:00"),
    ("ONE PIECE TCG","8-TBD","one-piece-tcg-premium-card-collection-best-selection-vol-7","https://x.com/ONEPIECE_tcg_EN/status/2067925359555690647","", "00:00"),
    ("ONE PIECE TCG","8-TBD","one-piece-tcg-premium-booster-vol-2","https://www.beckett.com/news/2026-tcg-release-dates-checklists-and-set-information/","", "00:00"),
    ("ONE PIECE TCG","8-TBD","one-piece-tcg-limited-card-sleeve-premium-matte-vol-6","https://x.com/ONEPIECE_tcg_EN/status/2067925359555690647","", "00:00"),
    # MTG
    ("MTG","8-7","mtg-the-hobbit-prerelease","https://magic.wizards.com/en/products/the-hobbit","https://www.beckett.com/news/2026-tcg-release-dates-checklists-and-set-information/", "00:00"),
    ("MTG","8-14","mtg-the-hobbit-global-release","https://magic.wizards.com/en/products/the-hobbit","https://x.com/wizards_magic/status/2082179288032219416", "00:00"),
    ("MTG","8-14","mtg-the-hobbit-gamegenic-18-pocket-zip-up-album-5-designs","https://x.com/Gamegenic_/status/2084308251391226217","", "00:00"),
    ("MTG","8-14","mtg-the-hobbit-gamegenic-premium-art-sleeves","https://x.com/Gamegenic_/status/2083221156203573464","", "00:00"),
    # YU-GI-OH!
    ("YU-GI-OH!","8-7","yu-gi-oh-blissful-eternity","https://www.beckett.com/news/2026-tcg-release-dates-checklists-and-set-information/","", "00:00"),
    # DISNEY LORCANA
    ("DISNEY LORCANA","8-TBD","disney-lorcana-attack-of-the-vine","https://www.beckett.com/news/2026-tcg-release-dates-checklists-and-set-information/","", "09:00"),
    # TOPPS
    ("TOPPS","8-10","2026-topps-universe-wwe","https://www.topps.com/pages/topps-universe-wwe","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-10","2026-bowman-chrome-baseball","https://www.topps.com/pages/bowman-chrome-baseball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-10","2026-topps-wacky-packages-all-new-series","https://www.topps.com/pages/2026-topps-wacky-packages-all-new-series","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-11","2026-topps-vault-marvel","https://www.topps.com/pages/topps-vault-marvel","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-11","topps-flagship-premier-league-2026-27","https://www.topps.com/pages/topps-flagship-premier-league","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-11","2026-topps-chrome-mls","https://www.topps.com/pages/topps-mls-chrome","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-12","2026-topps-pristine-baseball","https://www.topps.com/pages/topps-pristine-baseball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-12","2026-star-wars-chrome-galaxy","https://www.topps.com/pages/star-wars-chrome-galaxy","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-14","2026-topps-stadium-club-ufc","https://www.topps.com/pages/topps-stadium-club-ufc","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-17","2026-topps-museum-collection-baseball","https://www.topps.com/pages/topps-museum-collection-baseball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-18","2025-26-topps-definitive-basketball","https://www.topps.com/pages/topps-definitive-basketball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-19","2026-topps-chrome-baseball-logofractor-edition","https://www.topps.com/pages/topps-chrome-baseball-logofractor-edition","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-19","2026-topps-mint-marvel","https://www.topps.com/pages/topps-mint-marvel","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-20","2025-26-topps-motif-basketball","https://www.topps.com/pages/topps-motif-basketball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-27","2026-topps-chrome-black-basketball","https://www.topps.com/pages/topps-chrome-black-basketball","https://www.topps.com/release-calendar", "12:00"),
    ("TOPPS","8-TBD","2026-topps-flagship-football","https://www.beckett.com/news/sports-card-release-calendar-dates/","", "12:00"),
    ("TOPPS","8-TBD","2026-skybox-metal-universe-space-jam-30th","https://www.beckett.com/news/sports-card-release-calendar-dates/","", "12:00"),
    # PANINI
    ("PANINI","8-5","2026-panini-contenders-pfl","https://www.overtimecardsandcollectibles.com/product-release-schedule","", "12:00"),
    ("PANINI","8-TBD","2026-panini-flawless-fifa-world-cup","https://www.beckett.com/news/sports-card-release-calendar-dates/","", "12:00"),
    ("PANINI","8-TBD","2025-26-panini-select-road-to-fifa-world-cup-soccer","https://www.beckett.com/news/sports-card-release-calendar-dates/","", "12:00"),
    ("PANINI","8-TBD","2026-panini-impeccable-wnba","https://www.beckett.com/news/sports-card-release-calendar-dates/","", "12:00"),
    ("PANINI","8-TBD","2026-donruss-optic-nwsl-soccer","https://www.beckett.com/news/sports-card-release-calendar-dates/","", "12:00"),
    # NON-SPORTS CARDS
    ("NON-SPORTS CARDS","8-7","2026-leaf-seasons-in-the-sun-baseball","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/","", "12:00"),
    ("NON-SPORTS CARDS","8-TBD","2026-upper-deck-inspirations-world-of-dc","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/","", "12:00"),
    ("NON-SPORTS CARDS","8-TBD","2026-rittenhouse-star-trek-voyager","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/","", "12:00"),
    ("NON-SPORTS CARDS","8-TBD","2026-upper-deck-aew-wrestling","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/","", "12:00"),
    ("NON-SPORTS CARDS","8-TBD","2026-topps-chrome-sapphire-veefriends","https://www.beckett.com/news/2026-non-sports-cards-release-dates-checklists-and-set-information/","", "12:00"),
    # MATTEL CREATIONS
    ("MATTEL CREATIONS","8-TBD","mattel-creations-august-member-exclusive","https://creations.mattel.com/pages/launch-calendar","", "09:00"),
    ("MATTEL CREATIONS","8-TBD","hot-wheels-august-collector-exclusive","https://creations.mattel.com/pages/launch-calendar","", "09:00"),
    # SUPREME FW26
    ("SUPREME FW26","8-TBD","supreme-fw26-preview-lookbook","https://www.supremecommunity.com/season/fall-winter2026/droplists/","https://hypebeast.com/tags/weekly-drops", "11:00"),
    ("SUPREME FW26","8-TBD","supreme-fw26-week-1","https://www.supremecommunity.com/season/fall-winter2026/droplists/","https://hypebeast.com/tags/weekly-drops", "11:00"),
    ("SUPREME FW26","8-TBD","supreme-fw26-week-2","https://www.supremecommunity.com/season/fall-winter2026/droplists/","https://hypebeast.com/tags/weekly-drops", "11:00"),
    # COLLAB / LIFESTYLE
    ("COLLAB / LIFESTYLE","8-6","jjjjound-x-new-balance-740n-mushroom","https://jjjjound.com","https://hypebeast.com/tags/weekly-footwear-drops", "10:00"),
    ("COLLAB / LIFESTYLE","8-TBD","bobby-hundreds-x-disney-collab","https://thehundreds.com","https://supremedroplist.com/", "10:00"),
    ("COLLAB / LIFESTYLE","8-TBD","hellstar-x-adidas","https://www.adidas.com","https://hypebeast.com/tags/weekly-footwear-drops", "10:00"),
    ("COLLAB / LIFESTYLE","8-TBD","kith-august-monthly-drop","https://kith.com","https://hypebeast.com/tags/weekly-drops", "10:00"),
    ("COLLAB / LIFESTYLE","8-TBD","perks-and-mini-x-asics-collab","https://www.asics.com","https://hypebeast.com/tags/weekly-footwear-drops", "10:00"),
    # DISNEY PARKS PINS
    ("DISNEY PARKS PINS","8-4","wdw-august-le-pin-week-1","https://disneypinsblog.com","https://mypincentral.com", "09:00"),
    ("DISNEY PARKS PINS","8-11","wdw-august-le-pin-week-2","https://disneypinsblog.com","https://mypincentral.com", "09:00"),
    ("DISNEY PARKS PINS","8-14","d23-2026-anaheim-disney-pinnacle-booth","https://d23.com/d23-2026/","https://x.com/DisneyPinnacle/status/2081016173999862201", "09:00"),
    ("DISNEY PARKS PINS","8-14","d23-2026-disney-princess-all-13-le-pin-1200","https://d23.com/d23-2026/","https://x.com/DPrincess_Facts/status/2081016173999862201", "09:00"),
    ("DISNEY PARKS PINS","8-14","d23-2026-anaheim-exclusive-pin-drops-weekend","https://d23.com/d23-2026/","https://disneypinsblog.com", "09:00"),
    ("DISNEY PARKS PINS","8-18","wdw-august-le-pin-week-3","https://disneypinsblog.com","https://mypincentral.com", "09:00"),
    ("DISNEY PARKS PINS","8-25","wdw-august-le-pin-week-4","https://disneypinsblog.com","https://mypincentral.com", "09:00"),
    ("DISNEY PARKS PINS","8-TBD","wdw-halloween-2026-pin-series-launch","https://disneypinsblog.com/halloween-2026-pin-releases-at-disney-store-disney-parks/","", "09:00"),
    # VINYL & MUSIC
    ("VINYL & MUSIC","8-TBD","record-store-day-drops-2-2026","https://www.recordstoreday.com","", "00:00"),
    ("VINYL & MUSIC","8-TBD","august-limited-pressing-releases","https://www.plaidroomrecords.com/collections/pre-orders","", "00:00"),

    # ── VINYL & MUSIC — Pause & Play source ─────────────────────────────────
    # Aug 7 week
    ("VINYL & MUSIC","8-7","phoebe-bridgers-new-album-2026","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://pharmacyphotos.com", "00:00"),
    ("VINYL & MUSIC","8-7","alice-in-chains-mtv-unplugged-double-vinyl-reissue","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    ("VINYL & MUSIC","8-7","bob-marley-and-the-wailers-reissue-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-7","everything-but-the-girl-reissue-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-7","john-coltrane-reissue-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    # Aug 8 — Hamilton box set (Saturday release confirmed)
    ("VINYL & MUSIC","8-8","lin-manuel-miranda-rise-up-hamilton-anthology-7lp-box-set-10th-anniversary","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    # Aug 14 week — Leon Bridges white sand vinyl, Joy Oladokun transparent black ice
    ("VINYL & MUSIC","8-14","leon-bridges-happiness-anytime-white-sand-vinyl","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    ("VINYL & MUSIC","8-14","joy-oladokun-hope-is-a-heavy-thing-transparent-black-ice-vinyl","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    ("VINYL & MUSIC","8-14","nothing-but-thieves-stray-dogs-pink-rose-vinyl","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    ("VINYL & MUSIC","8-14","blondshell-violins-vinyl","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    # Aug 21 week — Paul Simon triple vinyl
    ("VINYL & MUSIC","8-21","paul-simon-the-quiet-celebration-concert-triple-vinyl","https://www.pauseandplay.com/release-dates/vinyl-releases/","https://www.pauseandplay.com/release-dates/on-the-cd-front/", "00:00"),
    # Aug 28 week — Nickelback, Nine Inch Nails, Marilyn Manson vinyl
    ("VINYL & MUSIC","8-28","nickelback-new-album-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-28","nine-inch-nails-new-album-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),
    ("VINYL & MUSIC","8-28","marilyn-manson-new-album-vinyl","https://www.pauseandplay.com/release-dates/on-the-cd-front/","https://www.pauseandplay.com/release-dates/vinyl-releases/", "00:00"),

    # PANINI — new confirmed from cardlines.com

    # PANINI — new confirmed from cardlines.com
    ("PANINI","8-12","2026-panini-prizm-baseball","https://cardlines.com/the-biggest-sports-card-releases-of-august-2026/","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("PANINI","8-12","2026-panini-revolution-k-league-soccer","https://www.checklistinsider.com/release-calendar","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("PANINI","8-12","2026-panini-turn-four-nascar-racing","https://www.checklistinsider.com/release-calendar","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("PANINI","8-19","2026-panini-donruss-wnba-basketball","https://cardlines.com/the-biggest-sports-card-releases-of-august-2026/","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("PANINI","8-19","2025-26-panini-origins-basketball","https://cardlines.com/the-biggest-sports-card-releases-of-august-2026/","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),

    # NON-SPORTS CARDS — confirmed
    ("NON-SPORTS CARDS","8-19","2025-26-upper-deck-clear-cut-hockey","https://cardlines.com/the-biggest-sports-card-releases-of-august-2026/","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),
    ("NON-SPORTS CARDS","8-19","2026-upper-deck-cfl-football","https://www.checklistinsider.com/release-calendar","https://www.beckett.com/news/sports-card-release-calendar-dates/", "12:00"),

    # VINYL — Nickelback and NIN confirmed week of 8/28 from pauseandplay
    # (already in file, keeping existing entries)

]


# ── DEDUPLICATE ───────────────────────────────────────────────────────────
def merge(manual, scraped):
    seen = set()
    out = []
    for d in manual:
        key = d[2][:40] if isinstance(d, tuple) else d["name"][:40]
        if key not in seen:
            seen.add(key)
            out.append(d)
    for d in scraped:
        key = d["name"][:40]
        if key not in seen:
            seen.add(key)
            out.append({
                "cat": d["cat"],
                "date": d["date"],
                "name": d["name"],
                "url1": d["url1"],
                "url2": d.get("url2",""),
            })
    return out


# ── SORT ──────────────────────────────────────────────────────────────────
def sort_key(d):
    if isinstance(d, tuple):
        date_str = d[1]
    else:
        date_str = d["date"]
    parts = str(date_str).split("-")
    try:
        return int(parts[1]) if parts[1] != "TBD" else 9999
    except:
        return 9999


# ── HTML BUILDER ──────────────────────────────────────────────────────────
def build_html(drops):
    import json as _json, re as _re, datetime as _dt

    MONTH_NUM  = _dt.date.today().month
    YEAR       = _dt.date.today().year
    month_name = _dt.date(YEAR, MONTH_NUM, 1).strftime("%B %Y")
    today_day  = _dt.date.today().day
    today_str  = _dt.date.today().strftime("%-m/%-d/%Y")

    CAT_TIMES = {
        "FUNKO POP":"11:00","TOPPS":"12:00","PANINI":"12:00",
        "POKEMON TCG":"09:00","ONE PIECE TCG":"00:00","MTG":"00:00",
        "YU-GI-OH!":"00:00","DISNEY LORCANA":"09:00","NON-SPORTS CARDS":"12:00",
        "DISNEY PARKS PINS":"09:00","SUPREME FW26":"11:00","MATTEL CREATIONS":"09:00",
        "COLLAB / LIFESTYLE":"10:00","VINYL & MUSIC":"00:00","MOVIES":"00:00",
    }

    def cslug(c): return _re.sub(r"[^a-z0-9]+"," ",c.lower()).strip().replace(" ","-")

    def get_fields(item):
        t = item
        return (t[0],t[1],t[2],t[3],
                t[4] if len(t)>4 else "",
                t[5] if len(t)>5 else CAT_TIMES.get(t[0],"09:00"))

    # JS drops (calendar — dated only)
    js_drops = []
    for item in drops:
        cat,date_str,name,url1,url2,time_et = get_fields(item)
        parts = str(date_str).split("-")
        try:
            day = int(parts[1]) if parts[1]!="TBD" else None
        except: day = None
        if not day: continue
        clean = _re.sub(r'^\d+-(?:TBD|\d+)-',"",name)
        js_drops.append({"cat":cat,"slug":cslug(cat),"day":day,"name":clean,
                         "url1":url1 if url1 and url1.startswith("http") else "",
                         "url2":url2 if url2 and url2.startswith("http") else "",
                         "time":time_et})

    # Table rows (all drops including TBD)
    table_rows = ""
    for item in drops:
        cat,date_str,name,url1,url2,time_et = get_fields(item)
        sl = cslug(cat)
        parts = str(date_str).split("-")
        try:
            day = parts[1]
            if day!="TBD":
                d = _dt.date(YEAR,int(parts[0]),int(day))
                date_display = d.strftime("%-m/%-d/%Y")
                date_sort = d.strftime("%Y%m%d")
            else:
                date_display = f"{parts[0]}/TBD/{YEAR}"; date_sort="99999999"
        except: date_display=date_str; date_sort="99999999"
        clean = _re.sub(r'^\d+-(?:TBD|\d+)-',"",name)
        try:
            h,m = map(int,time_et.split(":"))
            ampm = "AM" if h<12 else "PM"
            h12 = h if h<=12 else h-12
            if h12==0: h12=12
            time_display = f"{h12}:{str(m).zfill(2)} {ampm}"
        except: time_display = time_et
        u1 = f'<a href="{url1}" target="_blank" rel="noopener">Source 1 ↗</a>' if url1 and url1.startswith("http") else ""
        u2 = f'<a href="{url2}" target="_blank" rel="noopener">Source 2 ↗</a>' if url2 and url2.startswith("http") else ""
        table_rows += f'\n    <tr data-cat="{sl}" data-date="{date_sort}"><td class="date-cell">{date_display}</td><td class="time-cell">{time_display}</td><td class="name-cell">{clean}</td><td><span class="cat-badge cat-{sl}">{cat}</span></td><td class="source-cell">{u1}{" " if u1 and u2 else ""}{u2}</td></tr>'

    badge_css = btn_css = ""
    for cat,(bg,fg) in CAT_COLORS.items():
        sl = cslug(cat)
        badge_css += f".cat-{sl}{{background:{bg};color:{fg};}}\n"
        btn_css   += f'.filter-btn[data-filter="{sl}"].active{{background:{bg};color:{fg};border-color:{bg};}}\n'

    cats = sorted(set(get_fields(item)[0] for item in drops))
    filter_btns = '<button class="filter-btn active" data-filter="all">All</button>\n'
    for cat in cats:
        sl = cslug(cat)
        filter_btns += f'    <button class="filter-btn" data-filter="{sl}">{cat}</button>\n'

    CAT_MAP = {cslug(k): v[0] for k,v in CAT_COLORS.items()}

    LOGO_64_VAL  = LOGO_64
    LOGO_FAV_VAL = LOGO_FAV

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" type="image/png" href="{LOGO_FAV_VAL}">
<title>Grailz — {month_name} Drops</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#06060d;--surface:#0e0e1a;--border:#1e1230;--accent:#1eb8f0;--accent2:#9b3fe8;--accent3:#00e5ff;--text:#e8e8f8;--muted:#6b6b90;--row-alt:#0a0a14;}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Space Grotesk',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;}}
header{{border-bottom:1px solid var(--border);padding:18px 40px;background:linear-gradient(135deg,#06060d 60%,#0e0a1a 100%);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;}}
.logo-wrap{{display:flex;align-items:center;gap:14px;}}
.logo-img{{width:52px;height:52px;border-radius:50%;filter:drop-shadow(0 0 10px #9b3fe8) drop-shadow(0 0 20px #1eb8f060);flex-shrink:0;}}
.logo{{font-family:'Space Mono',monospace;font-size:42px;font-weight:700;background:linear-gradient(90deg,#fff 0%,#c084fc 35%,#9b3fe8 60%,#1eb8f0 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;letter-spacing:4px;line-height:1;filter:drop-shadow(0 0 18px #9b3fe870);}}
.subtitle{{font-size:12px;color:#8b6baa;letter-spacing:.16em;text-transform:uppercase;margin-top:6px;}}
.pill{{font-family:'Space Mono',monospace;font-size:11px;background:linear-gradient(135deg,#9b3fe820,#1eb8f020);border:1px solid #9b3fe860;color:#c084fc;padding:6px 16px;border-radius:20px;}}
.cal-section{{max-width:1100px;margin:28px auto 0;padding:0 32px;}}
.cal-top{{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;flex-wrap:wrap;gap:10px;}}
.view-toggle{{display:flex;gap:0;border:1px solid var(--border);border-radius:8px;overflow:hidden;}}
.view-btn{{font-family:'Space Mono',monospace;font-size:10px;font-weight:700;padding:6px 14px;border:none;background:transparent;color:var(--muted);cursor:pointer;letter-spacing:.06em;text-transform:uppercase;transition:all .15s;}}
.view-btn:hover{{background:#1a1a2a;color:var(--text);}}
.view-btn.active{{background:var(--accent2);color:#fff;}}
/* Week view */
.week-nav{{display:flex;align-items:center;gap:12px;margin-bottom:14px;}}
.week-nav-btn{{font-family:'Space Mono',monospace;font-size:18px;background:none;border:1px solid var(--border);color:var(--muted);width:32px;height:32px;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .15s;}}
.week-nav-btn:hover{{border-color:var(--accent2);color:var(--text);}}
.week-label{{font-family:'Space Mono',monospace;font-size:12px;color:var(--text);letter-spacing:.06em;}}
.week-table{{width:100%;border-collapse:collapse;border:1px solid var(--border);border-radius:12px;overflow:hidden;background:var(--surface);table-layout:fixed;}}
.week-table thead th{{font-family:'Space Mono',monospace;font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);text-align:center;padding:8px 4px;background:#0a0a14;border-bottom:1px solid var(--border);}}
.week-table thead th.week-th-today{{color:var(--accent2);}}
.week-cell{{height:140px;padding:8px 6px;vertical-align:top;border-right:1px solid var(--border);cursor:default;overflow:hidden;}}
.week-cell.has-drops{{background:#0d0b1a;cursor:pointer;}}
.week-cell.has-drops:hover{{background:#12101e;}}
.week-cell.selected{{background:#130f22;box-shadow:inset 0 0 0 2px var(--accent2);}}
.week-cell.week-today{{border-top:2px solid var(--accent2);}}
.week-date{{font-family:'Space Mono',monospace;font-size:11px;font-weight:700;color:var(--muted);margin-bottom:4px;}}
.week-cell.has-drops .week-date,.week-cell.week-today .week-date{{color:var(--text);}}
/* Day view */
.day-nav{{display:flex;align-items:center;gap:12px;margin-bottom:14px;}}
.day-nav-btn{{font-family:'Space Mono',monospace;font-size:18px;background:none;border:1px solid var(--border);color:var(--muted);width:32px;height:32px;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .15s;}}
.day-nav-btn:hover{{border-color:var(--accent2);color:var(--text);}}
.day-label{{font-family:'Space Mono',monospace;font-size:12px;color:var(--text);letter-spacing:.06em;}}
.day-view-inner{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px 24px;min-height:200px;}}
.day-empty{{text-align:center;padding:48px 0;color:var(--muted);font-family:'Space Mono',monospace;font-size:12px;}}
.day-drop-row{{display:flex;align-items:center;gap:10px;padding:10px 12px;background:#0a0a14;border-radius:6px;border:1px solid var(--border);margin-bottom:8px;flex-wrap:wrap;}}
.day-drop-row:last-of-type{{margin-bottom:0;}}
.day-drop-time{{font-family:'Space Mono',monospace;font-size:11px;color:var(--accent2);font-weight:700;white-space:nowrap;min-width:72px;}}
.day-drop-name{{font-size:12px;color:var(--text);flex:1;min-width:120px;}}
.day-srcs{{display:flex;gap:6px;flex-shrink:0;}}
.day-srcs a{{font-family:'Space Mono',monospace;font-size:9px;color:var(--accent3);text-decoration:none;border:1px solid #1eb8f030;padding:2px 7px;border-radius:3px;}}
.cal-title{{font-family:'Space Mono',monospace;font-size:14px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;}}
.cal-legend{{display:flex;flex-wrap:wrap;gap:8px;}}
.legend-item{{display:flex;align-items:center;gap:4px;font-size:10px;color:var(--muted);}}
.legend-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0;}}
.cal-table{{width:100%;border-collapse:collapse;border:1px solid var(--border);border-radius:12px;overflow:hidden;background:var(--surface);table-layout:fixed;}}
.cal-table thead th{{font-family:'Space Mono',monospace;font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);text-align:center;padding:10px 4px;background:#0a0a14;border-bottom:1px solid var(--border);width:14.28%;}}
.cal-cell{{height:100px;padding:6px 5px;vertical-align:top;border-right:1px solid var(--border);border-bottom:1px solid var(--border);cursor:default;transition:background .12s;overflow:hidden;position:relative;}}
.cal-cell.empty{{background:#08080f;}}
.cal-cell.has-drops{{background:#0d0b1a;cursor:pointer;}}
.cal-cell.has-drops:hover{{background:#12101e;}}
.cal-cell.selected{{background:#130f22;box-shadow:inset 0 0 0 2px var(--accent2);}}
.cal-cell.today .day-num{{background:var(--accent2);color:#fff;border-radius:50%;}}
.day-num{{font-family:'Space Mono',monospace;font-size:11px;font-weight:700;color:var(--muted);width:22px;height:22px;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-bottom:3px;}}
.cal-cell.has-drops .day-num{{color:var(--text);}}
.cal-chips{{display:flex;flex-direction:column;gap:2px;}}
.cal-chip{{font-size:9px;font-weight:600;padding:2px 5px;border-radius:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.4;}}
.cal-more{{font-size:8px;color:var(--muted);font-family:'Space Mono',monospace;padding-left:3px;}}
.day-panel{{max-width:1100px;margin:12px auto 0;padding:0 32px;display:none;}}
.day-panel.visible{{display:block;}}
.day-panel-inner{{background:var(--surface);border:1px solid #9b3fe850;border-radius:10px;padding:16px 20px;}}
.day-panel-title{{font-family:'Space Mono',monospace;font-size:12px;color:#c084fc;margin-bottom:12px;letter-spacing:.06em;}}
.panel-drop{{display:flex;align-items:center;gap:10px;padding:8px 12px;background:#0a0a14;border-radius:6px;border:1px solid var(--border);margin-bottom:6px;flex-wrap:wrap;flex-direction:row;}}
.panel-drop:last-of-type{{margin-bottom:0;}}
.panel-drop-name{{font-size:12px;color:var(--text);flex:1;min-width:120px;}}
.panel-srcs{{display:flex;gap:6px;flex-shrink:0;}}
.panel-srcs a{{font-family:'Space Mono',monospace;font-size:9px;color:var(--accent3);text-decoration:none;border:1px solid #1eb8f030;padding:2px 7px;border-radius:3px;}}
.drop-cal-row{{display:flex;align-items:center;gap:6px;margin-top:6px;flex-wrap:wrap;padding-top:6px;border-top:1px solid #1e1230;width:100%;}}
.drop-time-input{{background:#0e0e1a;border:1px solid var(--border);color:var(--text);font-family:'Space Mono',monospace;font-size:11px;padding:4px 8px;border-radius:5px;outline:none;-webkit-appearance:none;width:110px;}}
.drop-alert-num{{background:#0e0e1a;border:1px solid var(--border);color:var(--text);font-family:'Space Mono',monospace;font-size:11px;padding:4px 6px;border-radius:5px;outline:none;width:52px;}}
.drop-alert-unit{{background:#0e0e1a;border:1px solid var(--border);color:var(--text);font-family:'Space Mono',monospace;font-size:11px;padding:4px 6px;border-radius:5px;outline:none;cursor:pointer;}}
.btn-ics-sm{{font-family:'Space Mono',monospace;font-size:10px;font-weight:700;padding:5px 10px;border-radius:5px;border:none;cursor:pointer;background:linear-gradient(135deg,#9b3fe8,#1eb8f0);color:#fff;letter-spacing:.04em;text-transform:uppercase;transition:filter .15s;display:flex;align-items:center;gap:4px;white-space:nowrap;}}
.btn-ics-sm:hover{{filter:brightness(1.2);}}
/* per-drop cal export handled inline */
.divider{{max-width:1100px;margin:28px auto 0;padding:0 32px;display:flex;align-items:center;gap:12px;}}
.div-line{{flex:1;height:1px;background:var(--border);}}
.div-label{{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);white-space:nowrap;}}
.controls{{max-width:1100px;margin:16px auto 0;padding:0 32px;display:flex;flex-direction:column;gap:12px;}}
.search-wrap{{display:flex;align-items:center;gap:10px;}}
#search{{background:var(--surface);border:1px solid var(--border);color:var(--text);font-family:'Space Grotesk',sans-serif;font-size:14px;padding:9px 14px;border-radius:6px;width:280px;outline:none;}}
#search:focus{{border-color:var(--accent2);}}
#search::placeholder{{color:var(--muted);}}
.count{{font-size:12px;color:var(--muted);font-family:'Space Mono',monospace;}}
.filters{{display:flex;flex-wrap:wrap;gap:6px;}}
.filter-btn{{font-family:'Space Grotesk',sans-serif;font-size:11px;font-weight:600;padding:5px 12px;border-radius:20px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;transition:all .15s;letter-spacing:.04em;text-transform:uppercase;}}
.filter-btn:hover{{border-color:var(--text);color:var(--text);}}
.filter-btn.active{{background:var(--accent2);color:#fff;border-color:var(--accent2);}}
{btn_css}
.table-wrap{{max-width:1100px;margin:12px auto 0;padding:0 32px 60px;overflow-x:auto;}}
table.drop-table{{width:100%;border-collapse:collapse;font-size:13px;}}
table.drop-table thead th{{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);text-align:left;padding:10px 16px;border-bottom:1px solid var(--border);white-space:nowrap;cursor:pointer;user-select:none;}}
table.drop-table thead th:hover{{color:var(--text);}}
table.drop-table thead th.sorted::after{{content:' ↑';color:var(--accent3);}}
table.drop-table thead th.sorted.desc::after{{content:' ↓';}}
tbody tr{{border-bottom:1px solid #1e1e26;transition:background .1s;}}
tbody tr:nth-child(even){{background:var(--row-alt);}}
tbody tr:hover{{background:#100d1e;box-shadow:inset 3px 0 0 var(--accent2);}}
tbody tr.hidden{{display:none;}}
td{{padding:10px 16px;vertical-align:middle;}}.cal-table td{{padding:6px 5px;vertical-align:top;}}
.cat-badge{{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:3px 9px;border-radius:4px;white-space:nowrap;}}
{badge_css}
.date-cell{{font-family:'Space Mono',monospace;font-size:12px;color:var(--muted);white-space:nowrap;}}
.time-cell{{font-family:'Space Mono',monospace;font-size:11px;color:#9b3fe8;white-space:nowrap;font-weight:600;}}
.name-cell{{font-size:13px;color:var(--text);max-width:380px;}}
.source-cell{{display:flex;gap:8px;flex-wrap:wrap;}}
.source-cell a{{font-family:'Space Mono',monospace;font-size:10px;color:var(--accent3);text-decoration:none;border:1px solid #1eb8f030;padding:3px 8px;border-radius:4px;}}
.no-results{{text-align:center;padding:60px 0;color:var(--muted);font-family:'Space Mono',monospace;font-size:13px;display:none;}}
footer{{border-top:1px solid var(--border);padding:20px 40px;font-size:11px;color:var(--muted);font-family:'Space Mono',monospace;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;background:linear-gradient(135deg,#06060d,#0a0814);}}
@media(max-width:700px){{header,.cal-section,.day-panel,.divider,.controls,.table-wrap{{padding-left:16px;padding-right:16px;}}#search{{width:100%;}}.cal-cell{{height:72px;}}}}
</style>
</head>
<body>
<header>
  <div class="logo-wrap">
    <img src="{LOGO_64_VAL}" alt="Grailz" class="logo-img">
    <div><div class="logo">GRAILZ</div><div class="subtitle">Collectibles Drop Calendar</div></div>
  </div>
  <div class="pill">{month_name}</div>
</header>
<div class="cal-section">
  <div class="cal-top">
    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
      <div class="cal-title" id="calHeading">{month_name}</div>
      <div class="view-toggle">
        <button class="view-btn active" data-view="month">Month</button>
        <button class="view-btn" data-view="week">Week</button>
        <button class="view-btn" data-view="day">Day</button>
      </div>
    </div>
    <div class="cal-legend" id="legend"></div>
  </div>

  <!-- Month view -->
  <div id="viewMonth">
    <table class="cal-table">
      <thead><tr><th>Sun</th><th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th><th>Fri</th><th>Sat</th></tr></thead>
      <tbody id="calBody"></tbody>
    </table>
  </div>

  <!-- Week view -->
  <div id="viewWeek" style="display:none;">
    <div class="week-nav">
      <button class="week-nav-btn" id="weekPrev">‹</button>
      <span class="week-label" id="weekLabel"></span>
      <button class="week-nav-btn" id="weekNext">›</button>
    </div>
    <table class="week-table" id="weekTable">
      <thead id="weekHead"></thead>
      <tbody id="weekBody"></tbody>
    </table>
  </div>

  <!-- Day view -->
  <div id="viewDay" style="display:none;">
    <div class="day-nav">
      <button class="day-nav-btn" id="dayPrev">‹</button>
      <span class="day-label" id="dayLabel"></span>
      <button class="day-nav-btn" id="dayNext">›</button>
    </div>
    <div class="day-view-inner" id="dayViewInner"></div>
  </div>
</div>
<div class="day-panel" id="dayPanel">
  <div class="day-panel-inner">
    <div class="day-panel-title" id="panelTitle"></div>
    <div id="panelBody"></div>
  </div>
</div>
<div class="divider"><div class="div-line"></div><div class="div-label">Full Drop List</div><div class="div-line"></div></div>
<div class="controls">
  <div class="search-wrap">
    <input id="search" type="text" placeholder="Search drops…" autocomplete="off">
    <span class="count" id="count"></span>
  </div>
  <div class="filters">{filter_btns}</div>
</div>
<div class="table-wrap">
  <table class="drop-table">
    <thead><tr>
      <th data-col="0" class="sorted">Date</th>
      <th data-col="1">Time (ET)</th>
      <th data-col="2">Drop</th>
      <th data-col="3">Category</th>
      <th data-col="4">Sources</th>
    </tr></thead>
    <tbody id="tbody">{table_rows}</tbody>
  </table>
  <div class="no-results" id="noResults">No drops found.</div>
</div>
<footer>
  <span>Updated {today_str} · Grailz Discord Server</span>
  <span>topps.com · beckett.com · tcgradar.eu · disneypinsblog.com · funko.com + social</span>
</footer>
<script>
const DROPS={_json.dumps(js_drops)};
const CAT_MAP={_json.dumps(CAT_MAP)};
const MONTH_N={MONTH_NUM};
const YEAR_N={YEAR};
const TODAY_D={today_day};
const calBody=document.getElementById('calBody');
const panel=document.getElementById('dayPanel');
const panelTitle=document.getElementById('panelTitle');
const panelBody=document.getElementById('panelBody');
const legend=document.getElementById('legend');
const byDay={{}};
DROPS.forEach(d=>{{(byDay[d.day]=byDay[d.day]||[]).push(d);}});
const firstDow=new Date(YEAR_N,MONTH_N-1,1).getDay();
const daysInMonth=new Date(YEAR_N,MONTH_N,0).getDate();
let dayCount=0,row=document.createElement('tr'),selectedDay=null;
calBody.appendChild(row);
for(let i=0;i<firstDow;i++){{const td=document.createElement('td');td.className='cal-cell empty';row.appendChild(td);dayCount++;}}
for(let day=1;day<=daysInMonth;day++){{
  if(dayCount%7===0){{row=document.createElement('tr');calBody.appendChild(row);}}
  const dayDrops=byDay[day]||[];
  const td=document.createElement('td');
  td.className='cal-cell'+(dayDrops.length?' has-drops':'')+(day===TODAY_D?' today':'');
  td.dataset.day=day;
  const num=document.createElement('div');num.className='day-num';num.textContent=day;td.appendChild(num);
  if(dayDrops.length){{
    const chips=document.createElement('div');chips.className='cal-chips';
    dayDrops.slice(0,3).forEach(dr=>{{
      const chip=document.createElement('div');chip.className='cal-chip';
      chip.style.background=CAT_MAP[dr.slug]||'#2a2a35';chip.style.color='#fff';
      chip.title=dr.name;chip.textContent=dr.name;chips.appendChild(chip);
    }});
    if(dayDrops.length>3){{const m=document.createElement('div');m.className='cal-more';m.textContent='+'+(dayDrops.length-3)+' more';chips.appendChild(m);}}
    td.appendChild(chips);
    td.addEventListener('click',()=>{{
      if(selectedDay===day){{panel.classList.remove('visible');td.classList.remove('selected');selectedDay=null;return;}}
      const prev=calBody.querySelector('.selected');if(prev)prev.classList.remove('selected');
      selectedDay=day;td.classList.add('selected');
      const dt=new Date(YEAR_N,MONTH_N-1,day);
      panelTitle.textContent=dt.toLocaleDateString('en-US',{{weekday:'long',month:'long',day:'numeric',year:'numeric'}});
      panelBody.innerHTML='';
      dayDrops.forEach((dr,idx)=>{{
        const r=document.createElement('div');r.className='panel-drop';
        const bg=CAT_MAP[dr.slug]||'#2a2a35';
        const dropId='drop-'+day+'-'+idx;
        r.innerHTML=
          '<span class="cat-badge" style="background:'+bg+';color:#fff">'+dr.cat+'</span>'+
          '<span class="panel-drop-name">'+dr.name+'</span>'+
          '<span class="panel-srcs">'+
            (dr.url1?'<a href="'+dr.url1+'" target="_blank" rel="noopener">Source 1 ↗</a>':'')+
            (dr.url2?'<a href="'+dr.url2+'" target="_blank" rel="noopener">Source 2 ↗</a>':'')+
          '</span>'+
          '<div class="drop-cal-row">'+
            '<input type="time" class="drop-time-input" id="t-'+dropId+'" value="'+(dr.time||'09:00')+'">'+
            '<input type="number" class="drop-alert-num" id="n-'+dropId+'" value="30" min="1" max="10080">'+
            '<select class="drop-alert-unit" id="u-'+dropId+'">'+
              '<option value="minutes">Min</option>'+
              '<option value="hours">Hrs</option>'+
              '<option value="days">Days</option>'+
            '</select>'+
            '<button class="btn-ics-sm" data-id="'+dropId+'">'+
              '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>'+
              'Add'+
            '</button>'+
          '</div>';
        panelBody.appendChild(r);

        r.querySelector('.btn-ics-sm').addEventListener('click',()=>{{
          const t=document.getElementById('t-'+dropId).value||(dr.time||'09:00');
          const n=parseInt(document.getElementById('n-'+dropId).value)||30;
          const u=document.getElementById('u-'+dropId).value;
          const mins=u==='days'?n*1440:u==='hours'?n*60:n;
          exportICS(day,t,mins,[dr]);
        }});
      }});
      panel.classList.add('visible');panel.scrollIntoView({{behavior:'smooth',block:'nearest'}});
    }});
  }}
  row.appendChild(td);dayCount++;
}}
while(dayCount%7!==0){{const td=document.createElement('td');td.className='cal-cell empty';row.appendChild(td);dayCount++;}}
// ── View toggle ─────────────────────────────────────────────────────
let currentView='month';
let currentWeekStart=null;
let currentDayDate=null;
const viewMonth=document.getElementById('viewMonth');
const viewWeek=document.getElementById('viewWeek');
const viewDay=document.getElementById('viewDay');
const calHeading=document.getElementById('calHeading');
function getWeekStart(d){{const s=new Date(d);s.setDate(s.getDate()-s.getDay());s.setHours(0,0,0,0);return s;}}
function fmtShort(d){{return d.toLocaleDateString('en-US',{{month:'short',day:'numeric'}});}}
function fmt12(time){{if(!time)return'';const[h,m]=time.split(':').map(Number);const ap=h<12?'AM':'PM';const h12=h%12||12;return h12+':'+(m<10?'0'+m:m)+' '+ap;}}
currentWeekStart=getWeekStart(new Date(YEAR_N,MONTH_N-1,TODAY_D));
currentDayDate=new Date(YEAR_N,MONTH_N-1,TODAY_D);

function buildWeekView(){{
  const wHead=document.getElementById('weekHead');
  const wBody=document.getElementById('weekBody');
  const wLabel=document.getElementById('weekLabel');
  const days=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  const today=new Date(YEAR_N,MONTH_N-1,TODAY_D);
  const weekEnd=new Date(currentWeekStart);weekEnd.setDate(weekEnd.getDate()+6);
  wLabel.textContent=fmtShort(currentWeekStart)+' \u2013 '+fmtShort(weekEnd);
  wHead.innerHTML='';
  const hRow=document.createElement('tr');
  for(let i=0;i<7;i++){{
    const d=new Date(currentWeekStart);d.setDate(d.getDate()+i);
    const th=document.createElement('th');
    const isToday=d.toDateString()===today.toDateString();
    th.className=isToday?'week-th-today':'';
    th.innerHTML=days[i]+'<br><span style="font-size:11px;font-weight:400">'+d.getDate()+'</span>';
    hRow.appendChild(th);
  }}
  wHead.appendChild(hRow);
  wBody.innerHTML='';
  const bRow=document.createElement('tr');
  for(let i=0;i<7;i++){{
    const d=new Date(currentWeekStart);d.setDate(d.getDate()+i);
    const dayN=d.getDate(),monthN=d.getMonth()+1,yearN=d.getFullYear();
    const dayDrops=(monthN===MONTH_N&&yearN===YEAR_N)?byDay[dayN]||[]:[];
    const isToday=d.toDateString()===today.toDateString();
    const td=document.createElement('td');
    td.className='week-cell'+(dayDrops.length?' has-drops':'')+(isToday?' week-today':'');
    const dateDiv=document.createElement('div');dateDiv.className='week-date';
    dateDiv.textContent=monthN+'/'+dayN;td.appendChild(dateDiv);
    if(dayDrops.length){{
      dayDrops.slice(0,5).forEach(dr=>{{
        const chip=document.createElement('div');chip.className='cal-chip';
        chip.style.background=CAT_MAP[dr.slug]||'#2a2a35';chip.style.color='#fff';
        chip.style.marginBottom='2px';chip.title=dr.name;chip.textContent=dr.name;
        td.appendChild(chip);
      }});
      if(dayDrops.length>5){{const m=document.createElement('div');m.className='cal-more';m.textContent='+'+(dayDrops.length-5)+' more';td.appendChild(m);}}
      td.addEventListener('click',()=>{{currentDayDate=new Date(d);switchView('day');}});
    }}
    bRow.appendChild(td);
  }}
  wBody.appendChild(bRow);
}}

function buildDayView(){{
  const dInner=document.getElementById('dayViewInner');
  const dLabel=document.getElementById('dayLabel');
  dLabel.textContent=currentDayDate.toLocaleDateString('en-US',{{weekday:'long',month:'long',day:'numeric',year:'numeric'}});
  const dayN=currentDayDate.getDate(),monthN=currentDayDate.getMonth()+1,yearN=currentDayDate.getFullYear();
  const dayDrops=(monthN===MONTH_N&&yearN===YEAR_N)?byDay[dayN]||[]:[];
  dInner.innerHTML='';
  if(!dayDrops.length){{dInner.innerHTML='<div class="day-empty">No drops on this day.</div>';return;}}
  dayDrops.forEach((dr,idx)=>{{
    const row=document.createElement('div');row.className='day-drop-row';
    const bg=CAT_MAP[dr.slug]||'#2a2a35';
    const dropId='dv-'+dayN+'-'+idx;
    row.innerHTML=
      '<span class="day-drop-time">'+fmt12(dr.time||'09:00')+'</span>'+
      '<span class="cat-badge" style="background:'+bg+';color:#fff">'+dr.cat+'</span>'+
      '<span class="day-drop-name">'+dr.name+'</span>'+
      '<span class="day-srcs">'+
        (dr.url1?'<a href="'+dr.url1+'" target="_blank" rel="noopener">Source 1 \u2197</a>':'')+
        (dr.url2?'<a href="'+dr.url2+'" target="_blank" rel="noopener">Source 2 \u2197</a>':'')+
      '</span>'+
      '<div class="drop-cal-row">'+
        '<input type="time" class="drop-time-input" id="t-'+dropId+'" value="'+(dr.time||'09:00')+'">'+
        '<input type="number" class="drop-alert-num" id="n-'+dropId+'" value="30" min="1" max="10080">'+
        '<select class="drop-alert-unit" id="u-'+dropId+'">'+
          '<option value="minutes">Min</option><option value="hours">Hrs</option><option value="days">Days</option>'+
        '</select>'+
        '<button class="btn-ics-sm" data-id="'+dropId+'">'+
          '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>Add'+
        '</button>'+
      '</div>';
    row.querySelector('.btn-ics-sm').addEventListener('click',()=>{{
      const t=document.getElementById('t-'+dropId).value||(dr.time||'09:00');
      const n=parseInt(document.getElementById('n-'+dropId).value)||30;
      const u=document.getElementById('u-'+dropId).value;
      const mins=u==='days'?n*1440:u==='hours'?n*60:n;
      exportICS(dayN,t,mins,[dr]);
    }});
    dInner.appendChild(row);
  }});
}}

function switchView(v){{
  currentView=v;
  document.querySelectorAll('.view-btn').forEach(b=>b.classList.toggle('active',b.dataset.view===v));
  viewMonth.style.display=v==='month'?'block':'none';
  viewWeek.style.display=v==='week'?'block':'none';
  viewDay.style.display=v==='day'?'block':'none';
  if(v==='week')buildWeekView();
  if(v==='day')buildDayView();
  calHeading.textContent=v==='month'?'{month_name}':v==='week'?'Week View':'Day View';
}}
document.querySelectorAll('.view-btn').forEach(b=>{{
  b.addEventListener('click',()=>switchView(b.dataset.view));
}});
document.getElementById('weekPrev').addEventListener('click',()=>{{currentWeekStart.setDate(currentWeekStart.getDate()-7);buildWeekView();}});
document.getElementById('weekNext').addEventListener('click',()=>{{currentWeekStart.setDate(currentWeekStart.getDate()+7);buildWeekView();}});
document.getElementById('dayPrev').addEventListener('click',()=>{{currentDayDate.setDate(currentDayDate.getDate()-1);buildDayView();}});
document.getElementById('dayNext').addEventListener('click',()=>{{currentDayDate.setDate(currentDayDate.getDate()+1);buildDayView();}});

const seen={{}};
DROPS.forEach(d=>{{if(!seen[d.slug])seen[d.slug]={{cat:d.cat,color:CAT_MAP[d.slug]||'#2a2a35'}};}});
Object.entries(seen).sort((a,b)=>a[1].cat.localeCompare(b[1].cat)).forEach(([sl,info])=>{{
  const item=document.createElement('div');item.className='legend-item';
  item.innerHTML='<span class="legend-dot" style="background:'+info.color+'"></span>'+info.cat;
  legend.appendChild(item);
}});
function pad(n){{return String(n).padStart(2,'0');}}
function icsDate(y,m,d,time){{const[h,mi]=time.split(':').map(Number);return y+pad(m)+pad(d)+'T'+pad(h)+pad(mi)+'00';}}
function exportICS(day,time,alertMins,drops){{const CRLF=String.fromCharCode(13,10);
  const dt=new Date(YEAR_N,MONTH_N-1,day);
  const label=dt.toLocaleDateString('en-US',{{month:'long',day:'numeric',year:'numeric'}});
  const dtStr=icsDate(YEAR_N,MONTH_N,day,time);
  const[sh,sm]=time.split(':').map(Number);
  const dtEnd=icsDate(YEAR_N,MONTH_N,day,pad((sh+1)%24)+':'+pad(sm));
  const uid='grailz-'+YEAR_N+'-'+pad(MONTH_N)+'-'+pad(day)+'@grailzking.github.io';
  const desc=drops.map(d=>'['+d.cat+'] '+d.name+(d.url1?' — '+d.url1:'')).join('\\n');
  const names=drops.map(d=>d.name).join(', ');
  const ics=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Grailz//Drops Calendar//EN','CALSCALE:GREGORIAN','METHOD:PUBLISH',
    'BEGIN:VEVENT','UID:'+uid,'DTSTAMP:'+icsDate(YEAR_N,MONTH_N,day,'00:00'),
    'DTSTART:'+dtStr,'DTEND:'+dtEnd,'SUMMARY:🎯 Grailz Drop — '+label,
    'DESCRIPTION:'+desc.replace(/\\n/g,'\\\\n'),
    'BEGIN:VALARM','ACTION:DISPLAY','DESCRIPTION:Grailz Drop Reminder — '+names.slice(0,60),
    'TRIGGER:-PT'+alertMins+'M','END:VALARM','END:VEVENT','END:VCALENDAR'].join(CRLF);
  const blob=new Blob([ics],{{type:'text/calendar;charset=utf-8'}});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;a.download='grailz-drop-'+YEAR_N+'-'+pad(MONTH_N)+'-'+pad(day)+'.ics';
  document.body.appendChild(a);a.click();document.body.removeChild(a);URL.revokeObjectURL(url);
}}
const tbody=document.getElementById('tbody');
const rows=Array.from(tbody.querySelectorAll('tr'));
const noRes=document.getElementById('noResults');
const countEl=document.getElementById('count');
let activeFilter='all',sortCol=0,sortDesc=false;
function updateCount(){{const v=rows.filter(r=>!r.classList.contains('hidden')).length;countEl.textContent=v+' drop'+(v!==1?'s':'');}}
function applyFilters(){{
  const q=document.getElementById('search').value.toLowerCase();let any=false;
  rows.forEach(r=>{{const cm=activeFilter==='all'||r.dataset.cat===activeFilter;const tm=!q||r.textContent.toLowerCase().includes(q);r.classList.toggle('hidden',!(cm&&tm));if(cm&&tm)any=true;}});
  noRes.style.display=any?'none':'block';updateCount();
}}
document.querySelectorAll('.filter-btn').forEach(b=>{{b.addEventListener('click',()=>{{document.querySelectorAll('.filter-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');activeFilter=b.dataset.filter;applyFilters();}});}});
document.getElementById('search').addEventListener('input',applyFilters);
document.querySelectorAll('table.drop-table thead th[data-col]').forEach(th=>{{
  th.addEventListener('click',()=>{{
    const col=+th.dataset.col;if(sortCol===col)sortDesc=!sortDesc;else{{sortCol=col;sortDesc=false;}}
    document.querySelectorAll('table.drop-table thead th').forEach(t=>t.classList.remove('sorted','desc'));
    th.classList.add('sorted');if(sortDesc)th.classList.add('desc');
    rows.slice().sort((a,b)=>{{
      if(col===0){{const ad=a.dataset.date||'99999999',bd=b.dataset.date||'99999999';return sortDesc?bd.localeCompare(ad):ad.localeCompare(bd);}}
      const av=a.cells[col]?.textContent.trim()||'',bv=b.cells[col]?.textContent.trim()||'';return sortDesc?bv.localeCompare(av):av.localeCompare(bv);
    }}).forEach(r=>tbody.appendChild(r));applyFilters();
  }});
}});
applyFilters();
</script>
</body>
</html>"""



if __name__ == "__main__":
    print(f"\n=== Grailz Drops Builder — {MONTH} ===\n")

    # 1. Scrape sources
    scraped = []
    scraped += scrape_topps()
    scraped += scrape_beckett_tcg()
    scraped += scrape_beckett_nonsports()
    scraped += scrape_social()

    # 2. Merge with curated manual list
    all_drops = merge(MANUAL_DROPS, scraped)
    all_drops.sort(key=sort_key)
    print(f"\nTotal drops: {len(all_drops)} ({len(MANUAL_DROPS)} manual + {len(scraped)} scraped)")

    # 3. Build HTML
    html = build_html(all_drops)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Written → {OUTPUT_FILE}")
    print("\nDone. Push index.html to GitHub to deploy.\n")
