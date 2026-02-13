import re

test_html = '''
<img src="https://via.placeholder.com/100x100?text=Spaghetti" class="w-24 h-24">
<h3 class="font-bold text-lg">Spaghetti all'Assassina</h3>
'''

print('HTML di test:')
print(repr(test_html))

# Test semplice per le immagini
img_matches = re.findall(r'src="([^"]+)"', test_html)
print('URL immagini trovati:', img_matches)

# Test per i titoli
title_matches = re.findall(r'<h3[^>]*>([^<]+)</h3>', test_html)
print('Titoli trovati:', title_matches)

# Test con HTML più complesso
complex_html = '''
<div class="grid grid-cols-1 md:grid-cols-2 gap-8">
    <div class="bg-white p-4 rounded-xl shadow-md flex gap-4 items-start">
        <img src="https://via.placeholder.com/100x100?text=Spaghetti" class="w-24 h-24 object-cover rounded-lg flex-shrink-0">
        <div>
            <h3 class="font-bold text-lg">Spaghetti all'Assassina</h3>
            <p class="text-sm text-gray-600">Un piatto audace e irresistibile.</p>
        </div>
    </div>
    <div class="bg-white p-4 rounded-xl shadow-md flex gap-4 items-start">
        <img src="https://via.placeholder.com/100x100?text=Orecchiette" class="w-24 h-24 object-cover rounded-lg flex-shrink-0">
        <div>
            <h3 class="font-bold text-lg">Orecchiette alle Cime di Rapa</h3>
            <p class="text-sm text-gray-600">Piatto tipico pugliese.</p>
        </div>
    </div>
</div>
'''

print('\n\nHTML complesso:')
img_matches = re.findall(r'<img[^>]*src="([^"]+)"[^>]*>', complex_html)
print('URL immagini trovati:', img_matches)

# Prova a estrarre coppie immagine-titolo
card_pattern = r'<img[^>]*src="([^"]+)"[^>]*>.*?<h3[^>]*>([^<]+)</h3>'
cards = re.findall(card_pattern, complex_html, re.DOTALL)
print('Coppie immagine-titolo:', cards)