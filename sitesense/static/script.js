function initApp() {
   window.appManager = new AppManager();
  
    

}




let messageHistory = [];
let chatbotModeActive = false;
// Flag globale per disabilitare completamente la chatbar
// Abilitata di default: la linguetta e la chat devono essere visibili nelle pagine risultati
try { if (typeof window.__DISABLE_CHATBAR__ === 'undefined') window.__DISABLE_CHATBAR__ = false; if (typeof window.__FIRST_SEARCH_DONE__ === 'undefined') window.__FIRST_SEARCH_DONE__ = false; } catch (e) {}

// Pulizia al caricamento dell'area riservata per evitare mescolamento tra pagine
document.addEventListener('DOMContentLoaded', () => {
  try {
    const pathname = (window.location && window.location.pathname) || '';
    if (pathname.startsWith('/area_riservata')) {
      // Disabilita chatbar nell'area riservata
      window.__DISABLE_CHATBAR__ = true;
      const chatTab = document.getElementById('chat-toggle-tab');
      if (chatTab) chatTab.style.display = 'none';

      // CONTROLLA PRIMA se è un autosalvataggio
      const url = new URL(window.location.href);
      const autosalva = url.searchParams.get('autosalva');
      
      try { handleAutoSaveAfterLogin(); } catch (e) {}
      
      // Poi pulisci solo se NON è un autosalvataggio
      if (autosalva !== '1') {
        // Rimuovi flag e snapshot di ripristino
        try { clearRestoreSnapshots(); } catch (e) {}
        try { sessionStorage.removeItem('restore_results'); } catch (e) {}
        try { sessionStorage.removeItem('return_to_selection'); } catch (e) {}
        try { sessionStorage.removeItem('pending_search'); } catch (e) {}
        try { sessionStorage.removeItem('pending_itinerary_payload'); } catch (e) {}
        try { sessionStorage.removeItem('save_after_login'); } catch (e) {}

        // Reset stato
        try { window.manualSelection = []; } catch (e) {}
        try { messageHistory = []; } catch (e) {}
        try { chatbotModeActive = false; } catch (e) {}

        // Svuota contenitori se presenti
        try {
          const resultsContainer = document.getElementById('results-container');
          const mapContainer = document.getElementById('map-container');
          const categorizedContainer = document.getElementById('categorized-results-container');
          const selectionGrid = document.querySelector('#page-selection .selection-grid');
          if (resultsContainer) resultsContainer.innerHTML = '';
          if (mapContainer) mapContainer.innerHTML = '';
          if (categorizedContainer) categorizedContainer.innerHTML = '';
          if (selectionGrid) selectionGrid.innerHTML = '';
        } catch (e) {}

        // Nascondi risultati e chat se presenti
        try {
          const resultsSection = document.getElementById('results-section');
          const mapWrapper = document.getElementById('map-wrapper');
          const chatRightPanel = document.getElementById('chat-right-panel');
          if (resultsSection) resultsSection.classList.add('hidden');
          if (mapWrapper) mapWrapper.classList.add('hidden');
          if (chatRightPanel) chatRightPanel.classList.add('hidden');
        } catch (e) {}
      }
    }
  } catch (e) {}
});

class MapManager {
    constructor(mapElementId) {
        this.mapElement = document.getElementById(mapElementId);
        if (!this.mapElement) { console.error("Elemento mappa non trovato!"); return; }
        // Riduce il lampeggio: parte in fade-in quando i tiles sono pronti
        try {
            this.mapElement.style.opacity = '0';
            this.mapElement.style.transition = 'opacity 250ms ease';
            this.mapElement.style.willChange = 'opacity';
        } catch (e) {}
        const mapStyle = [{"elementType":"geometry","stylers":[{"color":"#242f3e"}]},{"elementType":"labels.text.fill","stylers":[{"color":"#746855"}]},{"elementType":"labels.text.stroke","stylers":[{"color":"#242f3e"}]},{"featureType":"administrative.locality","elementType":"labels.text.fill","stylers":[{"color":"#d59563"}]},{"featureType":"poi","elementType":"labels.text.fill","stylers":[{"color":"#d59563"}]},{"featureType":"poi.park","elementType":"geometry","stylers":[{"color":"#263c3f"}]},{"featureType":"poi.park","elementType":"labels.text.fill","stylers":[{"color":"#6b9a76"}]},{"featureType":"road","elementType":"geometry","stylers":[{"color":"#38414e"}]},{"featureType":"road","elementType":"geometry.stroke","stylers":[{"color":"#212a37"}]},{"featureType":"road","elementType":"labels.text.fill","stylers":[{"color":"#9ca5b3"}]},{"featureType":"road.highway","elementType":"geometry","stylers":[{"color":"#746855"}]},{"featureType":"road.highway","elementType":"geometry.stroke","stylers":[{"color":"#1f2835"}]},{"featureType":"road.highway","elementType":"labels.text.fill","stylers":[{"color":"#f3d19c"}]},{"featureType":"transit","elementType":"geometry","stylers":[{"color":"#2f3948"}]},{"featureType":"transit.station","elementType":"labels.text.fill","stylers":[{"color":"#d59563"}]},{"featureType":"water","elementType":"geometry","stylers":[{"color":"#17263c"}]},{"featureType":"water","elementType":"labels.text.fill","stylers":[{"color":"#515c6d"}]},{"featureType":"water","elementType":"labels.text.stroke","stylers":[{"color":"#17263c"}]}];
        this.map = new google.maps.Map(this.mapElement, { center: { lat: 41.9, lng: 12.5 }, zoom: 5, styles: mapStyle, mapTypeControl: false, streetViewControl: false });
        try {
            google.maps.event.addListenerOnce(this.map, 'tilesloaded', () => {
                try { this.mapElement.style.opacity = '1'; } catch (e) {}
            });
        } catch (e) {}
        this.directionsService = new google.maps.DirectionsService();
        this.distanceService = new google.maps.DistanceMatrixService();
        this.directionsRenderer = new google.maps.DirectionsRenderer({ suppressMarkers: true, polylineOptions: { strokeColor: "#00aaff", strokeWeight: 5 } });
        this.directionsRenderer.setMap(this.map);
        this.markers = [];
        this.bounds = null;
		this.hasAutoFitted = false;
    }

    orderActivitiesByDistance(originActivity, activities) {
    return new Promise((resolve, reject) => {
        const destinations = activities.map(a => a.location);

        this.distanceService.getDistanceMatrix({
            origins: [originActivity.location],
            destinations,
            travelMode: google.maps.TravelMode.DRIVING,
            unitSystem: google.maps.UnitSystem.METRIC
        }).then(response => {
            const elements = response.rows[0].elements;

            const ordered = activities.map((act, i) => ({
                activity: act,
                distance: elements[i].distance.value
            }))
            .sort((a, b) => a.distance - b.distance)
            .map(o => o.activity);

            resolve(ordered);
        }).catch(reject);
    });
}






    updateItinerary(activities) {
        this.markers.forEach(marker => marker.setMap(null));
        this.markers = [];
        this.directionsRenderer.setDirections({ routes: [] });
        if (!activities) return;
        const validActivities = (activities || []).filter(
            act => act && act.location && typeof act.location.lat === 'number' && typeof act.location.lng === 'number'
        );
        if (validActivities.length === 0) {
            console.warn('MapManager.updateItinerary: nessuna attività valida con coordinate lat/lng.');
            return;
        }

        // Rimuove duplicati di coordinate identiche per evitare ZERO_RESULTS nelle Directions
        const seen = new Set();
        const uniqueActivities = validActivities.filter(act => {
            const { lat, lng } = act.location || {};
            const key = `${Number(lat).toFixed(6)},${Number(lng).toFixed(6)}`;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        });

        this.bounds = new google.maps.LatLngBounds();
        uniqueActivities.forEach((activity, i) => {
            const marker = new google.maps.Marker({
                position: activity.location,
                map: this.map,
                label: `${i + 1}`,
                title: activity.name,
            });
            this.markers.push(marker);
            const infoWindow = new google.maps.InfoWindow({ content: `<strong>${activity.name}</strong><br>${activity.address}` });
            marker.addListener('click', () => infoWindow.open(this.map, marker));
            this.bounds.extend(activity.location);
        });

        if (uniqueActivities.length > 1) {
            const request = {
                origin: uniqueActivities[0].location,
                destination: uniqueActivities[uniqueActivities.length - 1].location,
                waypoints: uniqueActivities.slice(1, -1).map(p => ({ location: p.location, stopover: true })),
                optimizeWaypoints: false,
                travelMode: google.maps.TravelMode.DRIVING
            };
            this.directionsService.route(request, (result, status) => {
                if (status === 'OK') {
                    this.directionsRenderer.setDirections(result);
                } else {
                    console.warn('MapManager: routing DRIVING fallito:', status, result);
                    const altReq = { ...request, travelMode: google.maps.TravelMode.WALKING };
                    this.directionsService.route(altReq, (res2, status2) => {
                        if (status2 === 'OK') {
                            this.directionsRenderer.setDirections(res2);
                        } else {
                            console.warn('MapManager: fallback WALKING fallito:', status2, res2);
                        }
                    });
                }
            });
        } else {
            console.warn('MapManager.updateItinerary: meno di due punti unici, nessuna rotta calcolata.');
        }
        
        if (this.markers.length > 0) this.map.fitBounds(this.bounds);
		
			 if (!this.hasAutoFitted && this.bounds && !this.bounds.isEmpty()) {
           this.map.fitBounds(this.bounds);
           this.hasAutoFitted = true;
        }
    }

    refresh() {
        if (!this.map) return;
        try { google.maps.event.trigger(this.map, 'resize'); } catch (e) {}
        if (this.bounds && !this.bounds.isEmpty()) {
            this.map.fitBounds(this.bounds);
        }
    }
    
    
}

class AppManager {
    constructor() {
       
        window.mapManager = new MapManager('map-container');
        
        
    }

}






function snapshotResults() {
  const snapshots = {};
  const pages = ['intro','selection','lfw','map'];
  pages.forEach(p => {
    const el = document.getElementById(`page-${p}`);
    if (el) { snapshots[`snapshot_page_${p}`] = el.innerHTML; }
  });
  const mapWrapper = document.getElementById('map-wrapper');
  //if (mapWrapper) { snapshots['snapshot_map_wrapper'] = mapWrapper.innerHTML; }
  const cat = document.getElementById('categorized-results-container');
  if (cat) { snapshots['snapshot_categorized'] = cat.innerHTML; }
  const mapc = document.getElementById('map-container');
  //if (mapc) { snapshots['snapshot_map'] = mapc.innerHTML; }
  const chatRight = document.getElementById('chat-right-panel');
  if (chatRight) { snapshots['snapshot_chat_right'] = chatRight.innerHTML; }
  const chatMsgs = document.getElementById('chatbot-messages');
  if (chatMsgs) { snapshots['snapshot_chat_messages'] = chatMsgs.innerHTML; }
  try { snapshots['snapshot_message_history'] = JSON.stringify(messageHistory || []); } catch (e) {}
  Object.keys(snapshots).forEach(k => sessionStorage.setItem(k, snapshots[k]));
  sessionStorage.setItem('restore_results', '1');
}

let currentLocation = localStorage.getItem('sitesense_current_location') || null; // Variabile per memorizzare la località corrente

// DEBUG: Log della località caricata dal localStorage
console.log('🗺️ DEBUG - Località caricata dal localStorage:', currentLocation);

// Sanitizzazione cache: rimuovi valori non validi (stringa "null", vuoto, prodotti tipici)
try {
  const v = (currentLocation || '').toString().trim();
  const bannedNonLocations = ['orecchiette','cime','rapa','pasticciotti','taralli','carbonara','burrata','risotto','bistecca','vino','vini'];
  const isNullString = v.toLowerCase() === 'null';
  const isEmpty = v.length === 0;
  const isBanned = bannedNonLocations.includes(v.toLowerCase());
  if (isNullString || isEmpty || isBanned) {
    localStorage.removeItem('sitesense_current_location');
    currentLocation = null;
    console.log('🧹 Località in cache non valida rimossa');
  }
} catch (e) {}

// Sanitizzazione: rimuovi valori non-località rimasti in cache
try {
  const bannedNonLocations = ['orecchiette','cime','rapa','pasticciotti','taralli','carbonara','burrata','risotto','bistecca','vino','vini'];
  if (currentLocation && bannedNonLocations.includes(String(currentLocation).toLowerCase())) {
    localStorage.removeItem('sitesense_current_location');
    currentLocation = null;
    console.log('🧹 Località in cache non valida rimossa');
  }
} catch (e) {}

// Funzione per estrarre la località dalla query
function extractLocationFromQuery(query) {
  console.log('🔍 Tentativo di estrazione località dalla query:', query);
  
  // Lista di città e località italiane comuni
  const italianCities = [
    'Roma', 'Milano', 'Napoli', 'Torino', 'Palermo', 'Genova', 'Bologna', 'Firenze', 'Bari', 'Catania',
    'Venezia', 'Verona', 'Messina', 'Padova', 'Trieste', 'Brescia', 'Taranto', 'Prato', 'Parma', 'Modena',
    'Reggio Calabria', 'Reggio Emilia', 'Perugia', 'Livorno', 'Ravenna', 'Cagliari', 'Foggia', 'Rimini',
    'Salerno', 'Ferrara', 'Sassari', 'Latina', 'Giugliano', 'Monza', 'Siracusa', 'Pescara', 'Bergamo',
    'Forlì', 'Trento', 'Vicenza', 'Terni', 'Bolzano', 'Novara', 'Piacenza', 'Ancona', 'Andria', 'Arezzo',
    'Udine', 'Cesena', 'Lecce', 'Pesaro', 'Barletta', 'Alessandria', 'La Spezia', 'Pistoia', 'Catanzaro',
    'Brindisi', 'Treviso', 'Pisa', 'Caserta', 'Marsala', 'Varese', 'Massa', 'Como', 'Cosenza', 'Cremona'
  ];
  
  // Parole che NON sono località
  const nonLocationWords = [
    'Cosa', 'Dove', 'Come', 'Quando', 'Perché', 'Quale', 'Quanto', 'Chi', 'Dimmi', 'Vini', 'Ristoranti', 
    'Hotel', 'Pesce', 'Carne', 'Pizza', 'Pasta', 'Gelato', 'Caffè', 'Vino', 'Birra', 'Dolci', 'Antipasti',
    'Primi', 'Secondi', 'Contorni', 'Dessert', 'Colazione', 'Pranzo', 'Cena', 'Aperitivo', 'Cucina',
    'Ristorante', 'Trattoria', 'Osteria', 'Pizzeria', 'Bar', 'Pub', 'Locale', 'Posto', 'Posti', 'Luoghi',
    'Mangiare', 'Bere', 'Provare', 'Assaggiare', 'Gustare', 'Ordinare', 'Scegliere', 'Trovare', 'Cercare',
    'Buono', 'Buoni', 'Buona', 'Buone', 'Ottimo', 'Ottimi', 'Ottima', 'Ottime', 'Migliore', 'Migliori',
    'Tipico', 'Tipici', 'Tipica', 'Tipiche', 'Tradizionale', 'Tradizionali', 'Locale', 'Locali',
    'Specialità', 'Piatto', 'Piatti', 'Ricetta', 'Ricette', 'Ingrediente', 'Ingredienti',
    'Rapa', 'Pasticciotti', 'Taralli', 'Orecchiette', 'Cime', 'Carbonara', 'Burrata', 'Risotto', 'Bistecca'
  ];
  
  // Pattern più specifici per località
  const locationPatterns = [
    // Pattern con preposizioni specifiche per luoghi (rimosso 'di' per evitare catture tipo "cime di rapa")
    /\b(?:a|in|da|per|su|verso|presso|vicino a|zona|quartiere)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b/i,
    // Pattern per città seguite da regioni
    /\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:Puglia|Basilicata|Calabria|Sicilia|Sardegna|Campania|Lazio|Toscana|Umbria|Marche|Abruzzo|Molise|Emilia-Romagna|Liguria|Piemonte|Valle d'Aosta|Lombardia|Trentino|Veneto|Friuli)\b/i
  ];
  
  // Prima controlla se c'è una città italiana conosciuta nella query
  for (const city of italianCities) {
    const cityRegex = new RegExp(`\\b${city}\\b`, 'i');
    if (cityRegex.test(query)) {
      console.log('🗺️ Città italiana riconosciuta:', city);
      return city;
    }
  }
  
  // Poi usa i pattern per estrarre località
  for (let i = 0; i < locationPatterns.length; i++) {
    const pattern = locationPatterns[i];
    const matches = query.match(pattern);
    console.log(`🔍 Pattern ${i + 1} risultato:`, matches);
    
    if (matches) {
      const location = matches[1] || matches[0];
      console.log('🔍 Località candidata:', location);
      
      // Verifica che non sia una parola non-località e che sia abbastanza lunga
      if (location && 
          !nonLocationWords.some(word => word.toLowerCase() === location.toLowerCase()) && 
          location.length > 2 && 
          /^[A-Za-z\s]+$/.test(location)) { // Solo lettere e spazi
        console.log('🗺️ Località estratta dalla query:', location);
        return location;
      }
    }
  }
  
  console.log('❌ Nessuna località trovata nella query');
  return null;
}
  
function getCategoryDisplayName(category) {
  // Trasforma la categoria in un nome visualizzabile (es. 'hotel_consigliati' -> 'Hotel consigliati')
  const formatted = category.replace(/_/g, ' ');
  return formatted.charAt(0).toUpperCase() + formatted.slice(1);
}

function getCategoryIcon(category) {
  // Restituisce un'icona testuale per alcune categorie note
  const c = (category || '').toLowerCase();
  if (/hotel|strutture\s*ricettive/.test(c)) return '🏨';
  if (/vini|enoteca|cantine/.test(c)) return '🍷';
  if (/cucina\s*tipica|ristoranti|trattorie|osterie|pizzerie/.test(c)) return '🍽️';
  return '';
}


function removeMarkdownWrappers(content) {
  // Rimuove wrapper markdown come ```html, ```, ```javascript, etc.
  return content.replace(/```[a-zA-Z]*\n?/g, '').replace(/```/g, '');
}

function stripDocumentWrappers(html) {
  // Rimuove Doctype e tag documento per l'inserimento inline
  let out = html.replace(/<!DOCTYPE[\s\S]*?>/gi, '')
                .replace(/<html[\s\S]*?>/gi, '')
                .replace(/<\/html>/gi, '')
                .replace(/<head[\s\S]*?<\/head>/gi, '')
                .replace(/<body[\s\S]*?>/gi, '')
                .replace(/<\/body>/gi, '');
  // Rimuove script esterni non necessari (es. tailwind)
  out = out.replace(/<script[\s\S]*?<\/script>/gi, '');
  return out;
}

// Gestione pulsante "Elimina" nella pagina area riservata
function attachDeleteProgramHandlers() {
  if (typeof window === 'undefined') return;
  const isReservedArea = window.location && window.location.pathname === '/area_riservata';
  if (!isReservedArea) return;

  const buttons = document.querySelectorAll('.btn-delete-program');
  const modal = document.getElementById('delete-confirm-modal');
  const confirmBtn = document.getElementById('confirm-delete-btn');
  const cancelBtn = document.getElementById('cancel-delete-btn');
  if (!buttons || buttons.length === 0 || !modal || !confirmBtn || !cancelBtn) return;

  // Stato pendente dell'eliminazione
  let pendingDelete = { programId: null, card: null, triggerBtn: null };

  // Apri il modal al click su Elimina
  buttons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const programId = btn.getAttribute('data-program-id');
      const card = btn.closest('.city-card');
      if (!programId || !card) return;
      pendingDelete = { programId: Number(programId), card, triggerBtn: btn };
      modal.style.display = 'flex';
    });
  });

  // Conferma eliminazione
  confirmBtn.addEventListener('click', async (e) => {
    e.preventDefault();
    if (!pendingDelete.programId) { modal.style.display = 'none'; return; }
    const { programId, card, triggerBtn } = pendingDelete;
    try {
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Eliminazione...';
      const res = await fetch('/api/delete_program', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ program_id: programId })
      });
      const data = await res.json().catch(() => ({ success: false, error: 'Risposta non valida' }));
      if (data && data.success) {
        if (card) { card.remove(); }
        const cards = document.querySelector('.cards');
        if (cards && cards.children.length === 0) {
          const msg = document.createElement('p');
          msg.textContent = 'Nessun programma salvato.';
          cards.appendChild(msg);
        }
      } else {
        alert('Errore durante l\'eliminazione: ' + (data && data.error ? data.error : '')); 
      }
    } catch (err) {
      alert('Errore di rete durante l\'eliminazione');
    } finally {
      // Ripristina stato UI e chiudi modal
      confirmBtn.disabled = false;
      confirmBtn.textContent = 'Sì';
      modal.style.display = 'none';
      if (triggerBtn) {
        try { triggerBtn.blur(); } catch (e) {}
      }
      pendingDelete = { programId: null, card: null, triggerBtn: null };
    }
  });

  // Annulla eliminazione
  cancelBtn.addEventListener('click', (e) => {
    e.preventDefault();
    modal.style.display = 'none';
    pendingDelete = { programId: null, card: null, triggerBtn: null };
  });
}

document.addEventListener('DOMContentLoaded', () => {
  try { attachDeleteProgramHandlers(); } catch (e) {}
});

 function getCityIntroHTML(city) {
 
  return `
    <section id="city-intro-section" class="w-full rounded-xl mb-9 ml-6 mr-0">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3 top-5px items-center px-0 md:px-0 -mt-8    ">
        <div>
          
        </div>
      </div>
    </section>
  `;
} 





 function insertCityIntroSection(city) {
  if (!city) return;
  const introPage = document.getElementById('page-intro');
  if (!introPage) return;
  const existing = document.getElementById('city-intro-section');
  if (existing) {
    return;
  }
  const wrapper = document.createElement('div');
  wrapper.innerHTML =getCityIntroHTML(city);
  const section = wrapper.firstElementChild;
  try { section.className = 'w-full rounded-xl mb-4 mt-0 ml-5 mr-0'; } catch (e) {}
  introPage.insertBefore(section, introPage.firstChild);
} 
 


function toPlainText(html) {
  const temp = document.createElement('div');
  temp.innerHTML = html;
  const text = temp.textContent || '';
  return text.replace(/\s+/g, ' ').trim();
}

// rimosso il renderer di card piatti per annullare l'operazione

// Funzione per generare l'HTML dell'animazione di caricamento AI
function getAILoadingHTML(searchTerm) {
  return `
  <style>
    :root { --color-liquid:#004d26; --color-shell:#e0e0e0; --logo-url:url('https://www.initalya.it/initalya.svg'); --l-width:350px; --l-height:120px; }
    #preloader { display:flex; justify-content:center; align-items:center; background: transparent; padding: 0; border-radius: 0; box-shadow: none; margin-top: 64px; }
    .logo-box { position:relative; width:var(--l-width); height:var(--l-height); }
    .logo-shell { position:absolute; inset:0; background:var(--logo-url) no-repeat center; background-size:contain; opacity:.2; filter:grayscale(1); }
    .liquid-layer { position:absolute; left:0; bottom:0; width:100%; height:0%; background:var(--color-liquid); -webkit-mask-image:var(--logo-url); mask-image:var(--logo-url); -webkit-mask-size:var(--l-width) var(--l-height); mask-size:var(--l-width) var(--l-height); -webkit-mask-repeat:no-repeat; -webkit-mask-position:center bottom; transition:height .1s linear; }
    .liquid-layer::after { content:""; position:absolute; top:-10px; left:0; width:100%; height:20px; background:rgba(255,255,255,.2); filter:blur(5px); }
    .fade-out { opacity:0; pointer-events:none; }
  </style>
  <div id="preloader"><div class="logo-box"><div class="logo-shell"></div><div id="liquid" class="liquid-layer"></div></div></div>
  <div class="text-center mt-4">
    <h3 class="text-xl font-semibold text-slate-800 mb-2">Sto preparando il tour</h3>
    <p id="loading-status" class="text-slate-600">${searchTerm ? 'Ricerca: "' + searchTerm + '"' : ''}</p>
    <div class="ai-progress-bar mt-4 bg-slate-200 rounded-full overflow-hidden mx-auto" style="width: 256px; height: 4px;">
      <div class="ai-progress-fill h-full bg-gradient-to-r from-blue-500 to-purple-600 rounded-full"></div>
    </div>
  </div>
  `;
}

// (rimosso) Overlay globale al click: non più necessario

function showAILoadingAnimation(searchTerm) {
  // Fix: Rimosso blocco su chatbotModeActive/Toggle per permettere animazione su Home nelle ricerche successive
  if (window.__FIRST_SEARCH_DONE__ !== false && window.__SUPPRESS_HOME_OVERLAY__) {
    return;
  }
  
  // Importante: nascondi results-section per evitare che stillLoading() termini subito l'animazione
  try {
      const resultsSection = document.getElementById('results-section');
      if (resultsSection) {
         resultsSection.classList.add('hidden');
         resultsSection.style.display = 'none';
      }
  } catch(e) {}

  const homeHero = document.getElementById('home-hero');
  if (homeHero) {
    homeHero.style.display = 'block';
    homeHero.innerHTML = getAILoadingHTML(searchTerm);
    try {
      (function(){
        const liquid = document.getElementById('liquid');
        const preloader = document.getElementById('preloader');
        const homeHero = document.getElementById('home-hero');
        const resultsSection = document.getElementById('results-section');
        if (!liquid || !preloader) return;
        let progress = 0;
        const stillLoading = function(){
          const resultsVisible = !!(resultsSection && !resultsSection.classList.contains('hidden'));
          return !resultsVisible && homeHero && homeHero.offsetParent !== null;
        };
        const interval = setInterval(function(){
          if (!stillLoading()) {
            clearInterval(interval);
            setTimeout(function(){ preloader.classList.add('fade-out'); }, 200);
            return;
          }
          progress += 0.5;
          if (progress > 100) progress = 0;
          liquid.style.height = progress + '%';
        }, 30);
      })();
    } catch (e) {}
    // Nascondi il pannello del chatbot durante il caricamento
    try {
      const chatRightPanel = document.getElementById('chat-right-panel');
      if (chatRightPanel) {
        chatRightPanel.classList.add('hidden');
        chatRightPanel.style.display = 'none';
      }
    } catch (e) {}
    // Nascondi anche la barra della chat/form durante il caricamento
    try {
      const searchForm = document.getElementById('search-form');
      const resultsFormSlot = document.getElementById('results-form-slot');
      const chatFormContainer = document.getElementById('chat-right-form-container');
      if (searchForm) searchForm.style.display = 'none';
      if (resultsFormSlot) resultsFormSlot.style.display = 'none';
      if (chatFormContainer) chatFormContainer.style.display = 'none';
    } catch (e) {}
    // Nascondi il copyright in alto durante il caricamento AI
    try {
      const topCopyright = document.getElementById('home-top-copyright');
      if (topCopyright) {
        topCopyright.classList.add('hidden');
        topCopyright.style.display = 'none';
      }
    } catch (e) {}
  }
}

// Aggiorna la visibilità del pannello chat in base allo stato della sezione risultati
function updateChatPanelVisibility() {
  try {
    const resultsSection = document.getElementById('results-section');
    const resultsInner = document.getElementById('results-inner-container');
    const chatRightPanel = document.getElementById('chat-right-panel');
    const searchForm = document.getElementById('search-form');
    const resultsFormSlot = document.getElementById('results-form-slot');
    const chatFormContainer = document.getElementById('chat-right-form-container');
    const aiLoading = document.querySelector('.ai-loading-container');
    const programLoader = document.getElementById('program-loader');
    const resultsVisible = !!(resultsSection && !resultsSection.classList.contains('hidden'));
    // Considera il caricamento AI solo se il container è effettivamente visibile
    const isAiLoadingVisible = !!(aiLoading && aiLoading.offsetParent !== null);
    const isLoading = !!(isAiLoadingVisible || programLoader);
    const userWantsChatVisible = !!window.__CHAT_TOGGLE_VISIBLE__;
    // Assicura che la linguetta esista quando i risultati diventano visibili
    if (resultsVisible && !window.__DISABLE_CHATBAR__) { try { ensureChatToggle(); } catch (e) {} }

    // Blocca e nascondi sempre la chatbar se disabilitata globalmente
    

    // Adatta la larghezza del contenuto risultati: piena quando chat nascosta
    try {
      if (resultsVisible && resultsInner) {
        if (!isLoading && userWantsChatVisible) {
          const pr = (chatRightPanel && chatRightPanel.offsetWidth) ? (chatRightPanel.offsetWidth + 'px') : '320px';
          resultsInner.style.paddingRight = pr;
        } else {
          resultsInner.style.paddingRight = '0';
        }
      }
      const mapWrapper = document.getElementById('map-wrapper');
      if (mapWrapper) {
        if (!isLoading && userWantsChatVisible) {
          const pr = (chatRightPanel && chatRightPanel.offsetWidth) ? (chatRightPanel.offsetWidth + 'px') : '320px';
          mapWrapper.style.paddingRight = pr;
        } else {
          mapWrapper.style.paddingRight = '0';
        }
      }
    } catch (e) {}

    if (!chatRightPanel) return;
    const tabEl = document.getElementById('chat-toggle-tab');
    const isMobile = innerWidth <= 558;


   if (resultsVisible && !isLoading){

     
      if (innerWidth <= 558) {

if (searchForm) searchForm.style.display = '';


if (resultsFormSlot) {
resultsFormSlot.style.display = '';
resultsFormSlot.style.width = '100%';
resultsFormSlot.style.maxWidth = '100%';
resultsFormSlot.style.borderRadius = '0';

}

if (chatFormContainer) chatFormContainer.style.display = ''; 

chatRightPanel.classList.remove('hidden');

chatRightPanel.style.display = '';

chatRightPanel.style.transition = 'transform 300ms ease';

if (userWantsChatVisible) {

chatRightPanel.style.transform = 'translateY(0)';

chatRightPanel.style.pointerEvents = '';

} else {

chatRightPanel.style.transform = 'translateY(100%)';

chatRightPanel.style.pointerEvents = 'none';

}

if (tabEl) {
    const isMobile = innerWidth <= 558;
    if (isMobile) {
      tabEl.style.left = '0';
      tabEl.style.right = '0';
      tabEl.style.width = '100%';
      tabEl.style.height = '20px';
      
      
      const chatPanel = document.getElementById('chat-right-panel');
      if (chatPanel) {
          const panelStyle = window.getComputedStyle(chatPanel);
          const panelBottom = parseFloat(panelStyle.bottom) || 64;
          const panelHeight = chatPanel.offsetHeight || (window.innerHeight * 0.7);
          
          if (userWantsChatVisible) {
             
              tabEl.style.bottom = (panelBottom + panelHeight - 1) + 'px';
          } else {
              tabEl.style.bottom = (panelBottom + 46) + 'px';
          }
          
      }

      tabEl.style.border='none';
    } else {
      tabEl.style.left = '';
      tabEl.style.right = '12px';
      tabEl.style.width = '';
      tabEl.style.height = '72px';
      
      const slot = document.getElementById('results-form-slot');
      const slotHeight = slot ? Math.max(slot.offsetHeight || 0, 56) : 64;
      tabEl.style.bottom = slotHeight + 'px';
    }
    tabEl.style.top = '';
  }

return;




   }   


  }




    
    const panelWidth = chatRightPanel.offsetWidth || 320;
    try { chatRightPanel.style.transition = 'transform 300ms ease'; } catch (e) {}
    try { if (tabEl) { tabEl.style.transition = 'right 300ms ease, top 200ms ease, bottom 200ms ease'; const __m = window.innerWidth <= 558; if (__m) { tabEl.style.top = ''; /* Mobile bottom handled elsewhere */ } else { tabEl.style.bottom = ''; tabEl.style.top = '0px'; } } } catch (e) {}
    chatRightPanel.classList.remove('hidden');
    chatRightPanel.style.display = '';
    if (resultsVisible && !isLoading && userWantsChatVisible) {

   






      chatRightPanel.style.transform = 'translateX(0)';
      chatRightPanel.style.pointerEvents = '';
      if (tabEl) tabEl.style.right = panelWidth + 'px';
      // Mostra barra chat (form) nelle pagine risultati
      try {
        if (searchForm) searchForm.style.display = '';
        if (resultsFormSlot) resultsFormSlot.style.display = '';
        resultsFormSlot.style.width = '1850px';
        resultsFormSlot.style.marginLeft = '0px';

        if (chatFormContainer) chatFormContainer.style.display = '';
        const slot = document.getElementById('results-form-slot');
        if (slot && chatRightPanel) {
          slot.style.width = panelWidth + 'px';
          slot.style.maxWidth = '90vw';
        }
      } catch (e) {}
    } else {
      chatRightPanel.style.transform = 'translateX(100%)';
      chatRightPanel.style.pointerEvents = 'none';
      if (tabEl) tabEl.style.right = '0px';
      // Nascondi barra chat durante caricamento o fuori dai risultati
      try {
        if (searchForm) searchForm.style.display = 'block';
        if (resultsFormSlot) resultsFormSlot.style.display = 'none';
        if (chatFormContainer) chatFormContainer.style.display = 'none';
      } catch (e) {}
    
  }
    try { updateChatToggleVisibility(); } catch (e) {}
    // Aggiorna la griglia Selezione: 4 colonne con chat visibile, 5 colonne con chat nascosta
    try {
      const grid = document.querySelector('#page-selection .selection-grid');
      if (grid) {
        grid.style.display = 'grid';
        grid.style.gap = '24px 16px';
        grid.style.alignItems = 'stretch';
        grid.style.justifyContent = 'start';
        grid.style.gridTemplateColumns = 'repeat(auto-fit, minmax(230px, 1fr))';
      }
    } catch (e) {}
  } catch (e) {}
}

// Crea una linguetta bianca sul bordo destro per mostrare/nascondere chat
function ensureChatToggle() {
  try {
    if (window.__DISABLE_CHATBAR__) return;
    let tab = document.getElementById('chat-toggle-tab');
    if (!tab) {
      tab = document.createElement('div');
      tab.id = 'chat-toggle-tab';
      tab.setAttribute('role', 'button');
      tab.setAttribute('aria-controls', 'chat-right-panel');
      tab.setAttribute('aria-pressed', 'false');
      tab.setAttribute('title', 'Mostra/Nascondi chat');
      tab.tabIndex = 0;
      // Stile base (desktop): linguetta verde verticale a destra
      Object.assign(tab.style, {
        position: 'fixed',
        right: '0',
        top: '0px',
        transform: 'none',
        width: '32px',
        height: '72px',
        background: '#0f3e34',
        color: '#ffffff',
        borderRadius: '10px 0 0 10px',
        border: '1px solid rgba(0,0,0,0.12)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: '9998',
        cursor: 'pointer',
        userSelect: 'none'
      });
      const label = document.createElement('div');
      Object.assign(label.style, {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#ffffff',
        gap: '2px',
        marginTop: '6px'
      });
      ['C','h','a','t'].forEach(ch => {
        const s = document.createElement('span');
        s.textContent = ch;
        Object.assign(s.style, {
          fontSize: '11px',
          fontWeight: '700',
          lineHeight: '1'
        });
        label.appendChild(s);
      });
      tab.appendChild(label);

      // Helper: stile condizionale per mobile/desktop
      function styleChatToggleTab(el) {
        const isMobile = window.innerWidth <= 558;
        const resultsFormSlot = document.getElementById('results-form-slot');
        const lbl = el.firstChild;

        if (isMobile) {
          const slotHeight = resultsFormSlot ? Math.max(resultsFormSlot.offsetHeight || 0, 56) : 64;
          el.style.background = '#ffffff';
          el.style.color = '#0f3e34';
          el.style.border = 'none';
         
          el.style.width = '100%';
          el.style.height = '20px';
          el.style.right = '0';
          el.style.left = '0';
          el.style.top = '';
          
          const chatPanel = document.getElementById('chat-right-panel');
          if (chatPanel) {
              const panelStyle = window.getComputedStyle(chatPanel);
              const panelBottom = parseFloat(panelStyle.bottom) || 64;
              const panelHeight = chatPanel.offsetHeight || (window.innerHeight * 0.7);
              
              if (window.__CHAT_TOGGLE_VISIBLE__) {
                  el.style.bottom = (panelBottom + panelHeight - 1) + 'px';
              } else {
                  el.style.bottom = (panelBottom + 46) + 'px';
              }
          } else {
              el.style.bottom = slotHeight + 'px';
          }
          el.style.zIndex = '9999';
          el.style.display = 'flex';
          el.style.alignItems = 'center';
          el.style.justifyContent = 'flex-end';
          el.style.paddingRight = '12px';

          try {
            if (lbl) {
              lbl.style.color = '#0f3e34'; // Fix visibility (was white)
              
              if (lbl.getAttribute('data-mode') !== 'icon') {
                lbl.innerHTML = '';
                const icon = document.createElement('span');
                icon.className = 'material-icons';
                icon.style.fontSize = '20px';
                icon.id = 'chat-toggle-icon';
                icon.style.color = '#0f3e34'; // Explicit color
                lbl.appendChild(icon);
                lbl.setAttribute('data-mode', 'icon');
              }
              const icon = lbl.querySelector('.material-icons');
              if (icon) {
                 icon.textContent = window.__CHAT_TOGGLE_VISIBLE__ ? 'expand_more' : 'expand_less';
                 icon.style.color = '#0f3e34';
              }
              lbl.style.marginTop = '0';
              lbl.style.flexDirection = 'row';
            }
          } catch (e) {}
        } else {
          el.style.left = ''; // Reset left (was 0 in mobile)
          el.style.justifyContent = 'center'; // Reset justify (was flex-end)
          el.style.paddingRight = ''; // Reset padding
          
          el.style.background = '#0f3e34';
          el.style.color = '#ffffff';
          el.style.border = '1px solid rgba(0,0,0,0.12)';
         
          el.style.width = '32px';
          el.style.height = '72px';
          el.style.borderRadius = '10px 0 0 10px';
          el.style.right = '0';
          el.style.top = '0px';
          el.style.bottom = '';
          el.style.zIndex = '9998';
          try {
            if (lbl) {
              if (lbl.getAttribute('data-mode') !== 'text') {
                lbl.innerHTML = '';
                ['C','h','a','t'].forEach(ch => {
                  const s = document.createElement('span');
                  s.textContent = ch;
                  Object.assign(s.style, {
                    fontSize: '11px',
                    fontWeight: '700',
                    lineHeight: '1'
                  });
                  lbl.appendChild(s);
                });
                lbl.setAttribute('data-mode', 'text');
              }
              lbl.style.flexDirection = 'column';
              lbl.style.gap = '2px';
              lbl.style.marginTop = '6px';
              Array.from(lbl.children).forEach(function(s) {
                s.style.fontSize = '11px';
                s.style.lineHeight = '1';
                s.style.color = '#ffffff';
              });
            }
          } catch (e) {}
        }
      }
      try { styleChatToggleTab(tab); } catch (e) {}

      tab.addEventListener('click', () => {
        window.__CHAT_TOGGLE_VISIBLE__ = !window.__CHAT_TOGGLE_VISIBLE__;
        tab.setAttribute('aria-pressed', window.__CHAT_TOGGLE_VISIBLE__ ? 'true' : 'false');
        try { updateChatPanelVisibility(); } catch (e) {}
        try { styleChatToggleTab(tab); } catch (e) {}
      });
      tab.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          window.__CHAT_TOGGLE_VISIBLE__ = !window.__CHAT_TOGGLE_VISIBLE__;
          tab.setAttribute('aria-pressed', window.__CHAT_TOGGLE_VISIBLE__ ? 'true' : 'false');
          try { updateChatPanelVisibility(); } catch (e) {}
          try { styleChatToggleTab(tab); } catch (e) {}
        }
      });
      try {
        window.addEventListener('resize', () => {
          try { styleChatToggleTab(tab); } catch (e) {}
        });
      } catch (e) {}

      document.body.appendChild(tab);
    } else {
      // Se esiste già, riallinea lo stile per il viewport corrente
      try {
        const resultsFormSlot = document.getElementById('results-form-slot');
        const isMobile = window.innerWidth <= 558;
        const lbl = tab.firstChild;

        if (isMobile) {
          const slotHeight = resultsFormSlot ? Math.max(resultsFormSlot.offsetHeight || 0, 56) : 64;
          tab.style.background = '#ffffff';
          tab.style.color = '#0f3e34';
          tab.style.border = '1px solid rgba(15,62,52,0.8)';
       
          tab.style.width = '100%';
          tab.style.height = '20px';
          tab.style.borderRadius = '12px 12px 0 0';
          tab.style.right = '0';
          tab.style.left = '0';
          tab.style.top = '';
          
          const chatPanel = document.getElementById('chat-right-panel');
          if (chatPanel) {
              const panelStyle = window.getComputedStyle(chatPanel);
              const panelBottom = parseFloat(panelStyle.bottom) || 64;
              const panelHeight = chatPanel.offsetHeight || (window.innerHeight * 0.7);
              
              if (window.__CHAT_TOGGLE_VISIBLE__) {
                  tab.style.bottom = (panelBottom + panelHeight - 1) + 'px';
              } else {
                  tab.style.bottom = (panelBottom + 46) + 'px';
              }
          } else {
              tab.style.bottom = slotHeight + 'px';
          }
          tab.style.zIndex = '9999';
          tab.style.display = 'flex';
          tab.style.alignItems = 'center';
          tab.style.justifyContent = 'center';

          try {
            if (lbl) {
              if (lbl.getAttribute('data-mode') !== 'icon') {
                lbl.innerHTML = '';
                const icon = document.createElement('span');
                icon.className = 'material-icons';
                icon.style.fontSize = '24px';
                icon.id = 'chat-toggle-icon';
                lbl.appendChild(icon);
                lbl.setAttribute('data-mode', 'icon');
              }
              const icon = document.getElementById('chat-toggle-icon');
              if (icon) {
                 icon.textContent = window.__CHAT_TOGGLE_VISIBLE__ ? 'expand_more' : 'expand_less';
              }
              lbl.style.marginTop = '0';
              lbl.style.flexDirection = 'row';
            }
          } catch (e) {}
        } else {
          tab.style.background = '#0f3e34';
          tab.style.color = '#ffffff';
          tab.style.border = '1px solid rgba(0,0,0,0.12)';
     
          tab.style.width = '32px';
          tab.style.height = '72px';
          tab.style.borderRadius = '10px 0 0 10px';
          tab.style.right = '0';
          tab.style.top = '0px';
          tab.style.bottom = '';
          tab.style.zIndex = '9998';
          try {
            if (lbl) {
              if (lbl.getAttribute('data-mode') !== 'text') {
                lbl.innerHTML = '';
                ['C','h','a','t'].forEach(ch => {
                  const s = document.createElement('span');
                  s.textContent = ch;
                  Object.assign(s.style, {
                    fontSize: '11px',
                    fontWeight: '700',
                    lineHeight: '1'
                  });
                  lbl.appendChild(s);
                });
                lbl.setAttribute('data-mode', 'text');
              }
              lbl.style.flexDirection = 'column';
              lbl.style.gap = '2px';
              lbl.style.marginTop = '6px';
              Array.from(lbl.children).forEach(function(s) {
                s.style.fontSize = '11px';
                s.style.lineHeight = '1';
                s.style.color = '#ffffff';
              });
            }
          } catch (e) {}
        }
      } catch (e) {}
    }
  } catch (e) {}
}

// Menu mobile in alto a destra con pannello bianco
function ensureMobileTopMenu(){
  try{
    const isMobile = window.innerWidth <= 558;
    let btn = document.getElementById('mobile-menu-button');
    let panel = document.getElementById('mobile-menu-panel');
    if(!isMobile){ if(btn) btn.remove(); if(panel) panel.remove(); return; }
    if(!btn){
      btn = document.createElement('button');
      btn.id = 'mobile-menu-button';
      btn.setAttribute('aria-label','Apri menu');
      Object.assign(btn.style,{ position:'fixed', top:'10px', left:'12px', width:'40px', height:'40px', borderRadius:'9999px', display:'flex', alignItems:'center', justifyContent:'center', background:'#ffffff', color:'#0f3e34', border:'1px solid rgba(15,62,52,0.2)', zIndex:'1002' });
      const ic = document.createElement('span'); ic.className = 'material-icons'; ic.textContent = 'menu'; ic.style.fontSize='22px'; btn.appendChild(ic);
      btn.addEventListener('click', function(){ window.__MOBILE_MENU_OPEN__ = !window.__MOBILE_MENU_OPEN__; update(); });
      document.body.appendChild(btn);
    }
    if(!panel){
      panel = document.createElement('div'); panel.id='mobile-menu-panel';
      Object.assign(panel.style,{ position:'fixed', top:'0', left:'0', bottom:'0', width:'75vw', maxWidth:'420px', background:'#ffffff', color:'#0f3e34', boxShadow:'8px 0 24px rgba(0,0,0,0.18)', borderRight:'1px solid rgba(15,62,52,0.12)', zIndex:'1001', transform:'translateX(-100%)', transition:'transform 320ms ease', display:'flex', flexDirection:'column', padding:'80px 24px' });
      const logo = document.createElement('img'); logo.src='/assets/logo.png'; logo.alt='Initalya'; Object.assign(logo.style,{ width:'96px', height:'auto', marginBottom:'20px', display:'block' }); panel.appendChild(logo);
      function link(text, href){ const a=document.createElement('a'); a.textContent=text; a.href=href; Object.assign(a.style,{ fontSize:'18px', fontWeight:'600', margin:'12px 0', color:'#0f3e34', textDecoration:'none' }); return a; }
      panel.appendChild(link('Chi siamo','/chi_siamo'));
      const bottom = document.createElement('div'); Object.assign(bottom.style,{ marginTop:'auto', fontSize:'12px', color:'#64748b' }); bottom.innerHTML = '<a href="/termini" style="color:#64748b;text-decoration:none;">Termini e condizioni</a><br/><a href="/privacy" style="color:#64748b;text-decoration:none;">Privacy policy</a>'; panel.appendChild(bottom);
      document.body.appendChild(panel);
      document.addEventListener('keydown', function(ev){ if(ev.key==='Escape'){ window.__MOBILE_MENU_OPEN__=false; update(); } });
    }
    function update(){ if(panel){ panel.style.transform = window.__MOBILE_MENU_OPEN__ ? 'translateX(0)' : 'translateX(-100%)'; panel.style.pointerEvents = window.__MOBILE_MENU_OPEN__ ? '' : 'none'; } }
    update();
  }catch(e){}
}

// Pulsante D (Area Riservata) visibile solo dopo login
function isUserAuthenticated() {
  try {
    const ck = document.cookie || '';
    return /(^|;\s*)auth=1\b/.test(ck) && /(^|;\s*)user_email=/.test(ck);
  } catch (e) { return false; }
}
function ensureDashboardButton() {
  try {
    let btn = document.getElementById('dashboard-btn');
    if (!isUserAuthenticated()) { if (btn) btn.remove(); return; }
    if (!btn) {
      btn = document.createElement('a');
      btn.id = 'dashboard-btn';
      btn.href = '/area_riservata';
      btn.setAttribute('aria-label','Area riservata');
      btn.title = 'Area riservata';
      Object.assign(btn.style, {
        position:'fixed', right:'12px', bottom:'12px', width:'44px', height:'44px',
        background:'#facc15', color:'#0f3e34', borderRadius:'9999px', display:'flex',
        alignItems:'center', justifyContent:'center', fontWeight:'800',
        boxShadow:'0 6px 14px rgba(0,0,0,0.18)', zIndex:'9999', textDecoration:'none'
      });
      btn.textContent = 'D';
      document.body.appendChild(btn);
    }
    btn.style.display = '';
  } catch (e) {}
}
function ensureMobileProfileButton() {
  try {
    const isMobile = window.innerWidth <= 558;
    const btn = document.getElementById('profile-button');
    const panel = document.getElementById('profile-menu-panel');
    const container = document.getElementById('profile-button-container');
    if (!btn || !container) return;
    if (isMobile) {
      if (btn.parentNode !== document.body) document.body.appendChild(btn);
      if (panel && panel.parentNode !== document.body) document.body.appendChild(panel);
    } else {
      if (btn.parentNode !== container) container.appendChild(btn);
      const sidebar = document.getElementById('left-sidebar');
      if (sidebar && panel && panel.parentNode !== sidebar) sidebar.appendChild(panel);
    }
  } catch (e) {}
}
// Inizializza il pulsante D all’avvio
try { window.addEventListener('DOMContentLoaded', () => { try { ensureDashboardButton(); } catch (e) {} try { ensureMobileTopMenu(); } catch (e) {} try { ensureMobileProfileButton(); } catch (e) {} }); window.addEventListener('resize', () => { try { ensureMobileTopMenu(); } catch (e) {} try { ensureMobileProfileButton(); } catch (e) {} }); } catch (e) {}

// Mostra la linguetta solo in modalità risultati e quando non si sta caricando
function updateChatToggleVisibility() {
  try {
    const tab = document.getElementById('chat-toggle-tab');
    if (!tab) return;
    const resultsSection = document.getElementById('results-section');
    const aiLoading = document.querySelector('.ai-loading-container');
    const programLoader = document.getElementById('program-loader');
    const resultsVisible = !!(resultsSection && !resultsSection.classList.contains('hidden'));
    const isAiLoadingVisible = !!(aiLoading && aiLoading.offsetParent !== null);
    const isLoading = !!(isAiLoadingVisible || programLoader);
    tab.style.display = (resultsVisible && !isLoading) ? '' : 'none';
    tab.setAttribute('aria-pressed', !!window.__CHAT_TOGGLE_VISIBLE__ ? 'true' : 'false');
  } catch (e) {}
}

// Funzione per nascondere l'animazione di caricamento
function hideAILoadingAnimation() {
    const resultsSection = document.getElementById('results-section');
    if (resultsSection) {
        resultsSection.classList.remove('hidden');
        resultsSection.style.display = '';
    }
    const categorizedContainer = document.getElementById('categorized-results-container');
    if (categorizedContainer && categorizedContainer.querySelector('.ai-loading-container')) {
        categorizedContainer.innerHTML = '';
    }
    const homeHero = document.getElementById('home-hero');
    if (homeHero && homeHero.querySelector('.ai-loading-container')) {
        homeHero.innerHTML = '';
    }
    // Riallinea la visibilità della chat al termine del caricamento AI
    try { updateChatPanelVisibility(); } catch (e) {}
}

// Funzione per processare e visualizzare il contenuto testuale
function processAndDisplayContent(payload) {
    const categorizedContainer = document.getElementById('categorized-results-container');
    const pageIntro = document.getElementById('page-intro');
    
    const homeHero = document.getElementById('home-hero');
    if (homeHero) { homeHero.style.display = 'none'; }
    const resultsSection = document.getElementById('results-section');
    if (resultsSection) {
        resultsSection.classList.remove('hidden');
        resultsSection.style.display = '';
    }
    try { ensureDashboardButton(); } catch (e) {}
    initResultsNav();
    // Abilita avanzamento sequenziale: Intro → Selezione → Suggerimenti → Mappa
    try { initSequentialScrollPageSwitch(); } catch (e) {}
    try {
      // Usa l’helper ufficiale per determinare la pagina attiva (prima visibile in ordine)
      const currentActive = (typeof getCurrentActivePage === 'function') ? getCurrentActivePage() : null;
      // Non forzare "intro" se l'utente ha già selezionato una pagina
      const userNavigated = !!(window.__USER_NAV_ACTIVE__);
      if (!userNavigated && (!currentActive || currentActive === 'intro')) {
        showResultsPage('intro');
      } else if (!userNavigated && currentActive && currentActive !== 'intro') {
        // Se per qualche motivo altre pagine risultano visibili, nascondile e resta su intro
        showResultsPage('intro');
      }
    } catch (e) {}
    const mapWrapper = document.getElementById('map-wrapper');
    if (mapWrapper) {
      const pageMap = document.getElementById('page-map');
      const isMapVisible = pageMap && !pageMap.classList.contains('hidden');
      if (!isMapVisible) { mapWrapper.classList.add('hidden'); }
    }
    // Chat nascosta di default anche entrando direttamente nei risultati
    if(window.innerWidth <= 558){
      window.__CHAT_TOGGLE_VISIBLE__ = false;
    }else{
      window.__CHAT_TOGGLE_VISIBLE__ = true;
    }

  
    try { ensureChatToggle(); } catch (e) {}
    try { updateChatToggleVisibility(); } catch (e) {}
    // Aggiorna visibilità pannello chat in base allo stato (risultati/caricamento)
    updateChatPanelVisibility();
    document.body.classList.remove('bg-[#0f3e34]');
    document.body.classList.add('bg-[#e8f6ef]');
    try {
      document.body.classList.remove('body-home-hero');
      document.body.classList.add('results-mode');
  try {
    document.querySelectorAll('#iubenda-cs-container, #iubenda-cs-embedded, .iubenda-cs-badge, .iubenda-iframe, [class*="iubenda"], [id*="iubenda"], iframe[src*="iubenda"], a[href*="iubenda"]').forEach(function(el){ if (el && el.tagName && el.tagName.toLowerCase() !== 'script') { el.remove(); } });
    var iubScript = document.querySelector('script[src*="iubenda.com/widgets"]');
    if (iubScript && iubScript.parentNode) iubScript.parentNode.removeChild(iubScript);
    document.body.style.overflow = '';
    document.documentElement.style.overflow = '';
    document.body.style.position = '';
    document.body.style.height = '';
    document.body.style.pointerEvents = '';
  } catch (e) {}
      try {
        document.querySelectorAll('#iubenda-cs-container, #iubenda-cs-embedded, .iubenda-cs-badge, .iubenda-iframe, [class*="iubenda"], [id*="iubenda"], iframe[src*="iubenda"], a[href*="iubenda"]').forEach(function(el){ if (el && el.tagName && el.tagName.toLowerCase() !== 'script') { el.remove(); } });
        var iubScript = document.querySelector('script[src*="iubenda.com/widgets"]');
        if (iubScript && iubScript.parentNode) iubScript.parentNode.removeChild(iubScript);
        document.body.style.overflow = '';
        document.documentElement.style.overflow = '';
        document.body.style.position = '';
        document.body.style.height = '';
        document.body.style.pointerEvents = '';
      } catch (e) {}
    } catch (e) {}

    // Ripristina la visibilità del contenitore se era stato nascosto
    if (categorizedContainer) {
        categorizedContainer.style.display = 'block';
        categorizedContainer.style.visibility = 'visible';
        categorizedContainer.style.opacity = '1';
    }
    //insertCityIntroSection(currentLocation);
    
    // Non nascondere l'animazione di caricamento se il container è vuoto (potrebbe essere stato appena pulito)
    if (categorizedContainer && categorizedContainer.innerHTML.trim() !== '') {
        hideAILoadingAnimation();
    }

    if (payload.answer) {
        messageHistory.push({ role: 'model', parts: [{ text: payload.answer }] });
        
        // Crea un elemento per il contenuto testuale e inseriscilo come primo elemento
        const contentSection = document.createElement('div');
        contentSection.className = 'w-full max-w-[1400px] ml-6 mr-0 mb-8 order-first';
        const cleaned = stripDocumentWrappers(removeMarkdownWrappers(payload.answer));
        contentSection.innerHTML = `
            <div class="content-response">
                ${cleaned}
            </div>
        `;

        if (pageIntro) {
            const duplicates = pageIntro.querySelectorAll('.content-response');
            duplicates.forEach((el) => { if (el.parentNode) { el.parentNode.remove(); } });
            const cityIntro = pageIntro.querySelector('#city-intro-section');
            if (cityIntro && cityIntro.parentNode === pageIntro) {
                pageIntro.insertBefore(contentSection, cityIntro.nextSibling);
            } else {
                pageIntro.insertBefore(contentSection, pageIntro.firstChild);
            }

            try {
              // Rimuovi solo contenuti da venue e link a Maps dentro il blocco,
              // senza mai eliminare l'intero .content-response
              const mapLinkSelector = 'a[href*="://maps.google"], a[href*="google.com/maps"], a[href*="goo.gl/maps"]';
              contentSection.querySelectorAll(mapLinkSelector).forEach((anchor) => {
                const parent = anchor.closest('.results-html-content, .card');
                if (parent) parent.remove(); else anchor.remove();
              });

              // Rimuovi card di venue eventualmente finite nel testo
              contentSection.querySelectorAll('.place-card, .place_details').forEach((el) => {
                const parent = el.closest('.card');
                if (parent) parent.remove(); else el.remove();
              });

              // Se il testo contiene una griglia risultati, rimuovi solo la griglia
              contentSection.querySelectorAll('.category-results').forEach((grid) => {
                grid.remove();
              });

              // Rimuovi blocchi non culinari della pagina 2 e 3 riconosciuti dai titoli
              const headingRegexes = [
                /la\s+nostra\s+selezione/i,
                /hotel|strutture\s*ricettive/i,
                /cucina\s*tipica/i,
                /ristoranti|trattorie|osterie|pizzerie|enoteche|cantine|\bbar\b|\bpub\b/i
              ];
              contentSection.querySelectorAll('h2, h3, h4').forEach((h) => {
                const text = (h.textContent || '').trim();
                if (!text) return;
                const matches = headingRegexes.some(rx => rx.test(text));
                if (matches) {
                  const section = h.closest('.mb-8, section, div');
                  if (section) section.remove();
                }
              });

              // Rimuovi griglie di attività tipiche della pagina 3
              contentSection.querySelectorAll('.activities-grid, .category-results').forEach((grid) => {
                grid.remove();
              });

              // Rimuovi card venue (pagina 3) se sono finite nella pagina 1
              contentSection.querySelectorAll('.activity-card').forEach((el) => {
                const pid = el.getAttribute('data-place-id') || (el.dataset && el.dataset.placeId);
                const hasMapsLink = !!el.querySelector('a[href*="maps.google"], a[href*="goo.gl/maps"]');
                const addBtn = el.querySelector('.add-to-trip-btn');
                if (pid || hasMapsLink || addBtn) {
                  const container = el.closest('.mb-8, section, div');
                  if (container && container !== contentSection) container.remove(); else el.remove();
                }
              });

              // Rimuovi pulsante "Carica altri suggerimenti" se appare nella pagina 1
              contentSection.querySelectorAll('.load-more-btn').forEach((btn) => {
                const wrap = btn.closest('div');
                if (wrap) wrap.remove(); else btn.remove();
              });

              // Rimuovi etichetta "Altri suggerimenti" intrusa
              contentSection.querySelectorAll('#lfw-left-label, .lfw-left-label').forEach((el) => { el.remove(); });

              // Rimuovi qualsiasi sezione con attributo data-category (tipica della pagina 3)
              contentSection.querySelectorAll('[data-category]').forEach((el) => {
                const container = el.closest('.mb-8, section, div');
                if (container && container !== contentSection) container.remove(); else el.remove();
              });

              // Rimuovi griglie di attività tipiche della pagina 3
              contentSection.querySelectorAll('.activities-grid, .category-results').forEach((grid) => {
                grid.remove();
              });

              // Rimuovi card venue (pagina 3) se sono finite nella pagina 1
              contentSection.querySelectorAll('.activity-card').forEach((el) => {
                const pid = el.getAttribute('data-place-id') || (el.dataset && el.dataset.placeId);
                const hasMapsLink = !!el.querySelector('a[href*="maps.google"], a[href*="goo.gl/maps"]');
                const addBtn = el.querySelector('.add-to-trip-btn');
                if (pid || hasMapsLink || addBtn) {
                  const container = el.closest('.mb-8, section, div');
                  if (container && container !== contentSection) container.remove(); else el.remove();
                }
              });


              // Rimuovi etichette testuali "Vini" residue (non heading), soltanto fuori dalla sezione vini
              Array.from(contentSection.querySelectorAll('*')).forEach((el) => {
                try {
                  const tx = (el.textContent || '').trim();
                  if (!tx || !/^vini$/i.test(tx)) return;
                  const isHeading = /^(H2|H3|H4)$/.test(el.tagName);
                  const inWines = !!el.closest('.wines-section');
                  const hasChildren = el.children && el.children.length > 0;
                  if (!isHeading && !inWines && !hasChildren) el.remove();
                } catch (e) {}
              });

              // Rimuovi eventuali pannelli "La nostra selezione" intrusi
              contentSection.querySelectorAll('.our-selection').forEach(el => {
                const cont = el.closest('.mb-8, section, div');
                if (cont) cont.remove(); else el.remove();
              });
            } catch (e) {}

            // Allinea a sinistra i riquadri nella prima pagina
            try { alignSectionCardGridsLeft(pageIntro); } catch (e) {}
            try { pullCardPanelsLeft(pageIntro); } catch (e) {}
            try { adjustSectionAlignment(pageIntro); } catch (e) {}
        }
        try {
          applyAllResultTransformations(contentSection);

          // Rimuovi etichette testuali "Vini" residue nella pagina introduttiva
          try {
            const intro = document.getElementById('page-intro');
            if (intro) {
              // Rimuovi qualsiasi etichetta isolata "Vini" fuori dalla sezione vini
              Array.from(intro.querySelectorAll('*')).forEach((el) => {
                const tx = (el.textContent || '').trim();
                const inWines = !!el.closest('.wines-section');
                if (/^vini$/i.test(tx) && !inWines) {
                  el.remove();
                }
              });
              // Rimuovi heading "Vini" (e "Vini & Bevande") fuori dalla sezione vini, ma NON "Vini Locali"
              Array.from(intro.querySelectorAll('h2, h3, h4')).forEach((h) => {
                const tx = (h.textContent || '').trim();
                const inWines = !!h.closest('.wines-section');
                if (/^vini(\s*&\s*bevande)?$/i.test(tx) && !inWines) {
                  h.remove();
                }
              });
            }
          } catch (e) {}

          const categorizedContainer = document.getElementById('categorized-results-container');
          if (categorizedContainer) {
            applyAllResultTransformations(categorizedContainer);
          }
          attachSaveItineraryHandlers();
        } catch (e) {}
        const preview = cleaned.replace(/\s+/g, ' ').slice(0, 280);
        appendChatMessage('model', toPlainText(preview));
        hideAILoadingAnimation();
        try {
          const retSel = sessionStorage.getItem('return_to_selection');
          const saveAfterLogin = sessionStorage.getItem('save_after_login');
          // Avanza alla Selezione solo se il flusso di login/salvataggio è attivo
          if (retSel === '1' && saveAfterLogin === '1') {
            try { window.__USER_NAV_ACTIVE__ = true; } catch (e) {}
            showResultsPage('selection');
            try { sessionStorage.removeItem('return_to_selection'); } catch (e) {}
          }
        } catch (e) {}
    } else {
        // Mostra errore nell'area principale
        const errorSection = document.createElement('div');
        errorSection.className = 'w-full max-w-5xl mx-auto mb-8 order-first';
        errorSection.innerHTML = '<div class="text-center py-8"><p class="text-red-600">Nessuna risposta testuale ricevuta.</p></div>';
        
        if (categorizedContainer) {
            categorizedContainer.insertBefore(errorSection, categorizedContainer.firstChild);
        }
    }
}


function processAndDisplayMap(payload) {
    try {
      if (payload && payload.tool_name === 'search_google_maps' && payload.tool_data) {
        // Memorizza i risultati categorizzati per il salvataggio della pagina "Altri suggerimenti"
        window.lastRankedResults = payload.tool_data;
      }
    } catch (e) {}
    const mapContainer = document.getElementById('map-container');
    const categorizedContainer = document.getElementById('categorized-results-container');
    
    const homeHero = document.getElementById('home-hero');
    if (homeHero) { homeHero.style.display = 'none'; }
    const resultsSection = document.getElementById('results-section');
    if (resultsSection) { 
      resultsSection.classList.remove('hidden');
      resultsSection.style.display = '';
    }
    const mapWrapper = document.getElementById('map-wrapper');
    const pageMap = document.getElementById('page-map');
    const isMapVisible = pageMap && !pageMap.classList.contains('hidden');
    if (mapWrapper) {
      if (isMapVisible) {
        mapWrapper.classList.remove('hidden');
        try { if (window.mapManager) setTimeout(() => window.mapManager.refresh(), 0); } catch (e) {}
      } else {
        mapWrapper.classList.add('hidden');
      }
    }
    // Aggiorna visibilità pannello chat in base allo stato (risultati/caricamento)
    updateChatPanelVisibility();
    document.body.classList.remove('bg-[#0f3e34]');
    document.body.classList.add('bg-[#e8f6ef]');

    // Ripristina la visibilità dei contenitori se erano stati nascosti
    if (mapContainer) {
        mapContainer.style.display = 'block';
        mapContainer.style.visibility = 'visible';
        mapContainer.style.opacity = '1';
    }
    if (categorizedContainer) {
        categorizedContainer.style.display = 'block';
        categorizedContainer.style.visibility = 'visible';
        categorizedContainer.style.opacity = '1';
    }
    //insertCityIntroSection(currentLocation);
    
    // Verifica se i contenitori sono stati appena puliti (potrebbero essere vuoti dopo clear_previous_content)
    if (!categorizedContainer) {
        console.warn('categorizedContainer non trovato, saltando processAndDisplayMap');
        return;
    }

  if (payload.tool_name === 'search_google_maps' && payload.tool_data) {
    const toolData = payload.tool_data;
    // Traccia se sono stati aggiunti contenuti alle pagine 2/3
    let selectionAdded = false;
    let lfwAdded = false;
    const categories = Object.keys(toolData);

        if (categories.length > 0) {
            // Inizializza contenitori delle pagine
            const pageIntro = document.getElementById('page-intro');
            const pageSelection = document.getElementById('page-selection');
            const pageLfw = document.getElementById('page-lfw');
            const pageMap = document.getElementById('page-map');
            // Non pulire i contenitori: accumuliamo sezioni per pagina
            categories.forEach(category => {
              const categoryData = toolData[category];
              if (categoryData.results) {
                const catLower = (category || '').toLowerCase();
                const categoryTitle = getCategoryDisplayName(category);
                const categoryIcon = getCategoryIcon(category);
                const categorySection = document.createElement('div');
                categorySection.className = 'mb-8 ml-6';

                    // Controlla il tipo di 'results' per decidere come renderizzare
                    if (typeof categoryData.results === 'string') {
                        // RANKING ATTIVO: 'results' è una stringa HTML
                        categorySection.innerHTML = `
                            <h3 class="text-2xl font-bold text-[#0f3e34] mb-6 flex items-center justify-center">
                              <span class="mr-3 text-3xl">${categoryIcon}</span>
                              ${categoryTitle}
                            </h3>
                            <div class="results-html-content" data-category="${category}">
                              ${categoryData.results}
                            </div>
                        `;
                        const contentEl = categorySection.querySelector('.results-html-content');
                        const gridEl = contentEl ? (contentEl.querySelector('.activities-grid') || contentEl.querySelector('.category-results')) : null;
                        if (gridEl) {
                          const cards = Array.from(gridEl.querySelectorAll('.activity-card'));
                          const links = Array.from(gridEl.querySelectorAll('a'));
                          const list = cards.length ? cards : links;
                          if (list.length > 4) {
                            list.slice(4).forEach(el => { el.style.display = cards.length ? 'none' : 'none'; });
                          }
                          const btn = categorySection.querySelector('.load-more-btn');
                          if (btn) {
                            let visibleCount = 4;
                            btn.dataset.offset = '4';
                            btn.addEventListener('click', () => {
                              const next = list.slice(visibleCount, visibleCount + 4);
                              next.forEach(el => { el.style.display = cards.length ? 'flex' : 'block'; });
                              visibleCount += next.length;
                              btn.dataset.offset = String(visibleCount);
                              if (visibleCount >= list.length) { btn.style.display = 'none'; }
                            });
                          }
                        }
                    } else if (Array.isArray(categoryData.results)) {
                        // RANKING DISATTIVO: 'results' è un array di luoghi
                        categorySection.innerHTML = `
                            <h3 class="text-2xl font-bold text-[#0f3e34] mb-6 flex items-center justify-center">
                              <span class="mr-3 text-3xl">${categoryIcon}</span>
                              ${categoryTitle}
                              <span class="ml-3 text-lg font-normal text-slate-500">(${categoryData.results.length} risultati)</span>
                            </h3>
                            <div class="grid category-results w-full justify-items-start" style="grid-template-columns: repeat(4, 300px); gap: 24px 16px;" data-category="${category}">
                            </div>
                        `;
                        const categoryResultsContainer = categorySection.querySelector(`[data-category="${category}"]`);
                        (categoryData.results || []).slice(0, 4).forEach(place => {
                            const card = document.createElement('a');
                            card.href = `/place_details?place_id=${place.place_id}`;
                            card.className = "flex flex-col bg-white rounded-xl shadow-lg overflow-hidden transition-all hover:shadow-xl duration-300 transform hover:-translate-y-1 w-[300px]";
                            card.innerHTML = `
                                ${place.foto_url ? `<div class="w-full bg-center bg-no-repeat aspect-[4/3] bg-cover" style='background-image: url("${place.foto_url}");'></div>` : '<div class="w-full bg-slate-200 aspect-[4/3] flex items-center justify-center"><span class="material-icons text-slate-400 text-4xl">place</span></div>'}
                                <div class="p-5 flex flex-col flex-grow">
                                  <h4 class="text-slate-800 text-lg font-semibold leading-snug">${place.nome || 'Nome non disponibile'}</h4>
                                  <p class="text-slate-600 text-sm font-normal leading-normal mt-1 flex-grow">${place.indirizzo || 'Indirizzo non disponibile'}</p>
                                  <p class="text-slate-500 text-xs font-normal leading-normal mt-1">Valutazione: ${place.valutazione || 'N/A'}</p>
                                </div>
                            `;
                            // Ripristino appendChild per mostrare i risultati
                            categoryResultsContainer.appendChild(card);
                        });
                    }
                    
                    // Instrada la sezione nella pagina corretta
                    let target;
                    const isFoodCategory = /(primi|secondi|prodotti(?:\s|_)*tipici|cibi|piatti|specialit(?:à|a))/.test(catLower);
                    const isVenueCategory = /(ristoranti|trattorie|osterie|pizzerie|pasticcerie|enoteche|cantine|bar|pub|locale|locali|hotel|strutture\s*ricettive|cucina\s*tipica|vini|)/.test(catLower);
                    const resultsIsArray = Array.isArray(categoryData.results);
                    const htmlStr = typeof categoryData.results === 'string' ? categoryData.results : '';
                    const containsVenueHtml = htmlStr ? /place_details|Vedi\s+su\s+Maps|href=\"https?:\/\/maps\.google/i.test(htmlStr) : false;
                    // Terza pagina (LFW) deve mostrare solo: hotel, vini, cucina tipica, dolci
                    const allowedThirdPage = /(hotel|strutture\s*ricettive|cucina\s*tipica|vini|dolci|pasticcerie|dessert|gelaterie|dolci_tradizionali)/.test(catLower) || (htmlStr ? /(hotel|cucina\s*tipica|vini|dolci|pasticcerie|dessert|gelaterie)/i.test(htmlStr) : false);
                    if (/la_nostra_selezione/.test(catLower)) {
                      target = pageSelection;
                      // Se abbiamo una selezione manuale dal JSON, NON rimuovere il pannello
                      // e salta l'append dei risultati server (verranno mostrati quelli manuali)
                      try {
                        if (!Array.isArray(manualSelection) || !manualSelection.length) {
                          pageSelection.querySelectorAll('.our-selection').forEach(n => {
                            const cont = n.closest('.mb-8.ml-6') || n.parentElement;
                            if (cont) cont.remove(); else n.remove();
                          });
                        }
                      } catch (e) {}
                    } else if (resultsIsArray || containsVenueHtml) {
                      // Instrada risultati venue solo se consentiti per la terza pagina
                      target = allowedThirdPage ? pageLfw : null;
                    } else if (isVenueCategory) {
                      target = allowedThirdPage ? pageLfw : null;
                    } else if (isFoodCategory) {
                      target = pageIntro;
                    } else {
                      target = allowedThirdPage ? pageLfw : null;
                    }
                    if (target) {
                      // Appendi sempre la sezione di categoria al target determinato
                      target.appendChild(categorySection);
                      // Segna pagine popolate
                      try {
                        if (target === pageSelection) selectionAdded = true;
                        if (target === pageLfw) lfwAdded = true;
                      } catch (e) {}
                    }

                    if (categoryData.iframe_url && mapContainer.innerHTML === '') {
                        mapContainer.innerHTML = `
                         
                        `;
                        const routeList = document.getElementById('route-list');
                        if (routeList) {
                          const items = [];
                          if (Array.isArray(categoryData.results)) {
                            categoryData.results.slice(0,5).forEach(p => items.push(p));
                          }
                          if (!items.length) {
                            // Prova altre categorie per riempire la lista
                            categories.forEach(cat => {
                              const cd = toolData[cat];
                              if (Array.isArray(cd?.results)) {
                                cd.results.slice(0,5-items.length).forEach(p => items.push(p));
                              }
                            });
                          }
                          routeList.innerHTML = items.slice(0,5).map(place => {
                            const name = place.name || place.nome || 'Senza nome';
                            const rating = place.rating || place.valutazione || 'N/A';
                            const address = place.formatted_address || place.indirizzo || '';
                            const price = place.price_level ? '€'.repeat(place.price_level) : '';
                            return `
                              <div class="bg-white/10 rounded-lg p-4">
                                <div class="flex items-center justify-between">
                                  <span class="font-semibold">${name}</span>
                                  <span class="text-sm">⭐ ${rating}</span>
                                </div>
                                ${price ? `<p class="text-white/80 text-xs mt-1">${price}</p>` : ''}
                                ${address ? `<p class="text-white/80 text-sm mt-1">${address}</p>` : ''}
                              </div>
                            `;
                          }).join('');
                        }
                    }
                }
            });
            const pageMapContainer = document.getElementById('page-map');
            const mapWrapper = document.getElementById('map-wrapper');
            try { ensureLfwStandardSections(toolData); } catch (e) {}
            // Nascondi overlay quando i contenuti richiesti sono pronti
            try {
              const activePage = (typeof getCurrentActivePage === 'function') ? getCurrentActivePage() : null;
              if (selectionAdded && (!activePage || activePage === 'selection')) { hideProgramLoading(); }
              if (lfwAdded && (!activePage || activePage === 'lfw')) { hideProgramLoading(); }
            } catch (e) {}
            try { attachSaveItineraryHandlers(); } catch (e) {}
            // Autosalvataggio cache città: salva una volta per sessione dopo il render live
            try {
              if (!window.usedCityCacheFallback) {
                maybeAutoSaveCityCache('live');
              }
            } catch (e) {}
        } else {
            if (categorizedContainer) {
                categorizedContainer.innerHTML = '<p class="text-slate-600">Nessun luogo trovato per la tua ricerca.</p>';
            }
        }
    }
  }


function initResultsNav() {
  const iconsNav = document.getElementById('results-icons');
  if (!iconsNav) return;
  const btns = iconsNav.querySelectorAll('button[data-page]');
  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      try { window.__USER_NAV_ACTIVE__ = true; } catch (e) {}
      const target = btn.getAttribute('data-page');
      showResultsPage(target);
      btns.forEach(b => {
        const img = b.querySelector('img');
        const defaultSrc = b.dataset.iconDefault;
        const activeSrc = b.dataset.iconActive;
        if (!img || !defaultSrc || !activeSrc) return;
        img.src = (b === btn) ? activeSrc : defaultSrc;
      });
    });
  });
}

// Flag di navigazione utente: disattivo all’avvio per bloccare switch automatici
try {
  if (typeof window.__USER_NAV_ACTIVE__ === 'undefined') window.__USER_NAV_ACTIVE__ = false;
} catch (e) {}

function showResultsPage(page) {
  try {
    if (window.__USER_NAV_ACTIVE__ === false && page !== 'intro') {
      return; // blocca switch automatici finché l’utente non naviga
    }
  } catch (e) {}
  const pages = ['intro','selection','lfw','map'];
  pages.forEach(p => {
    const el = document.getElementById(`page-${p}`);
    if (!el) return;
    if (p === page) el.classList.remove('hidden'); else el.classList.add('hidden');
  });
  // Assicura che il footer risultati sia sempre visibile su tutte le pagine
  try {
    const resultsFooter = document.getElementById('results-footer');
    if (resultsFooter) resultsFooter.classList.remove('hidden');
  } catch (e) {}
  // Overlay di caricamento specifici per pagine 2 e 3, persistenti fino al popolamento
  try {
    if (page === 'selection') {
      if (typeof showProgramLoading === 'function') showProgramLoading({ label: 'carica selezione', nonBlocking: true });
      // Se i contenuti della Selezione sono già presenti, nascondi subito l'overlay
      try {
        const grid = document.querySelector('#page-selection .selection-grid');
        const hasCards = grid && grid.children && grid.children.length > 0;
        const hasManual = Array.isArray(window.manualSelection) && window.manualSelection.length > 0;
        if (hasCards || hasManual) { if (typeof hideProgramLoading === 'function') hideProgramLoading(); }
      } catch (e) {}
    } else if (page === 'lfw') {
      if (typeof showProgramLoading === 'function') showProgramLoading({ label: 'carica altri suggerimenti', nonBlocking: true });
      
      // Se ci sono già contenuti, nascondi l'overlay
      try {
        const pageLfw = document.getElementById('page-lfw');
        const hasContent = pageLfw && pageLfw.children && pageLfw.children.length > 0;
        if (hasContent) { if (typeof hideProgramLoading === 'function') hideProgramLoading(); }
      } catch (e) {}

      // Prova a drenare la coda di reinserimenti quando la pagina LFW è attiva
      try { if (typeof drainPendingLfwActs === 'function') drainPendingLfwActs(); } catch (e) {}
    } else {
      // Su pagine diverse da 2 e 3, l'overlay deve sparire
      if (typeof hideProgramLoading === 'function') hideProgramLoading();
    }
  } catch (e) {}
  // Mostra il logo header solo nella pagina intro dei risultati
  try {
    const brandLogo = document.getElementById('brand-logo-header');
    if (brandLogo) {
      if (page === 'intro') {
        brandLogo.style.display = '';
        brandLogo.classList.remove('md:hidden');
      } else if (page === 'lfw') {
        brandLogo.style.display = '';
        brandLogo.classList.add('md:hidden');
      } else {
        brandLogo.style.display = 'none';
        brandLogo.classList.remove('md:hidden');
      }
    }
    


    const sidebarLogos = document.querySelectorAll('.sidebar-logo-toggle');
    sidebarLogos.forEach(logo => {
      let show = (page === 'selection'  || page === 'map' || page === 'lfw');
      // Fix: nascondi logo mobile (fixed) specificamente nella pagina lfw
      if (page === 'lfw' && logo.classList.contains('fixed')) {
        show = false;
      }
      logo.style.display = show ? '' : 'none';
    });
    // Toggle simbolo Iubenda: visibile solo su intro, nascosto su selection/lfw/map
    
  } catch (e) {}
  // Sfondo circoscritto: verde #0f3e34 SOLO per pagina Selezione
  try {
    document.body.classList.remove('body-selection-active');
    document.body.classList.remove('body-map-active');
    document.body.classList.remove('bg-[#e8f6ef]');
    document.body.classList.remove('bg-[#0f3e34]');
    if (page === 'selection') {
      document.body.classList.add('body-selection-active');
    } else if (page === 'map') {
      document.body.classList.add('body-map-active');
      document.body.classList.add('bg-[#0f3e34]');
    }
  } catch (e) {}
  const mapWrapper = document.getElementById('map-wrapper');
  if (mapWrapper) {
    if (page === 'map') {
      mapWrapper.classList.remove('hidden');
      try { if (window.mapManager) setTimeout(() => window.mapManager.refresh(), 0); } catch (e) {}
      //try {
       /*  const mapsScript = Array.from(document.scripts).find(s => s.src && s.src.includes('maps.googleapis.com/maps/api/js'));
        if (window.google && window.google.maps) {
          setTimeout(() => { if (window.initMap) window.initMap(); }, 0);
        } else if (mapsScript) {
          mapsScript.addEventListener('load', () => { if (window.initMap) window.initMap(); });
        }
      } catch (e) {} */
    } else {
      mapWrapper.classList.add('hidden');
    }
  }
  // Mostra il pulsante "salva itinerario" solo nella pagina selezione
  const saveContainer = document.getElementById('save-itinerary-container');
  if (saveContainer) {
    if (page === 'selection') {
	saveContainer.classList.remove('hidden');
    } else saveContainer.classList.add('hidden');
  
}
  // Contenitore risultati: sfondo verde SOLO per pagina Selezione
  const resultsSection = document.getElementById('results-section');
  if (resultsSection) {
    try {
      resultsSection.classList.remove('results-green-active');
      resultsSection.classList.remove('results-green-map');
      resultsSection.classList.toggle('results-green-selection', page === 'selection');
    } catch (e) {}
  }
  // Mostra/nascondi pulsante "salva ricerca" solo sulla pagina risultati 2
  try {
    const saveSearchBtn = document.getElementById('save-search-btn');
    if (saveSearchBtn) {
      const shouldShow = (page === 'selection');
      saveSearchBtn.classList.toggle('hidden', !shouldShow);
    }
  } catch (e) {}
 const iconsNav = document.getElementById('results-icons');
  if (iconsNav) {
    const btns = iconsNav.querySelectorAll('button[data-page]');
    btns.forEach((b, idx) => {
      const img = b.querySelector('img');
      const defaultSrc = b.dataset.iconDefault;
      const activeSrc = b.dataset.iconActive;
      if (!img || !defaultSrc || !activeSrc) return;
      const isActive = b.getAttribute('data-page') === page;
      img.src = isActive ? activeSrc : defaultSrc;
      img.classList.add('icona-brillante');
      if (idx === 1) {
        // Seconda icona: sempre pienamente opaca
        img.classList.add('opacity-100');
      } else {
        // Altre icone: non forziamo opacità piena
        img.classList.remove('opacity-100');
      }
    });
  }

  // Trigger salvataggio cache città quando le pagine 2 (selection) e 3 (lfw) sono visibili e hanno contenuti
  try {
    if (page === 'selection') {
      const grid = document.querySelector('#page-selection .selection-grid');
      const hasCards = grid && grid.children && grid.children.length > 0;
      const hasManual = Array.isArray(window.manualSelection) && window.manualSelection.length > 0;
      if (hasCards || hasManual) {
        if (typeof maybeAutoSaveCityCache === 'function') maybeAutoSaveCityCache('page_selection');
      }
    } else if (page === 'lfw') {
      const pageLfw = document.getElementById('page-lfw');
      const hasContent = pageLfw && pageLfw.children && pageLfw.children.length > 0;
      const ranked = (typeof window.lastRankedResults === 'object' && window.lastRankedResults) ? window.lastRankedResults : null;
      const hasRanked = ranked && Object.keys(ranked).length > 0;
      if (hasContent || hasRanked) {
        if (typeof maybeAutoSaveCityCache === 'function') maybeAutoSaveCityCache('page_lfw');
      }
    }
  } catch (e) {}
}

// Auto avanzamento: quando si arriva in fondo alla pagina, attiva la successiva
function getCurrentActivePage() {
  try {
    const pages = ['intro','selection','lfw','map'];
    for (let p of pages) {
      const el = document.getElementById(`page-${p}`);
      if (el && !el.classList.contains('hidden')) return p;
    }
  } catch (e) {}
  return null;
}

function getNextPage(current) {
  const order = ['intro','selection','lfw','map'];
  const idx = order.indexOf(current);
  if (idx === -1) return null;
  if (idx < order.length - 1) return order[idx + 1];
  return null; // nessuna pagina successiva dopo 'map'
}

function initAutoAdvanceOnScroll() {
  // Disattivato su richiesta: non auto-avanzare quando si raggiunge il fondo
  return;
  let lock = false;
  const threshold = 120; // margine per evitare avanzamenti immediati su pagine corte

  const handler = () => {
    if (lock) return;
    try {
      const doc = document.documentElement;
      // Evita auto-avanzamento se la pagina è più corta o uguale all'altezza del viewport
      if (doc.scrollHeight <= window.innerHeight + threshold) return;
      const atBottom = (window.scrollY + window.innerHeight) >= (doc.scrollHeight - threshold);
      if (!atBottom) return;
      const current = getCurrentActivePage();
      // Non auto-avanzare dalla pagina Intro: serve azione esplicita dell'utente
      if (current === 'intro') return;
      const next = getNextPage(current);
      if (!next) return;

      lock = true;
      try { showResultsPage(next); } catch (e) {}
      // Reset dello scroll in alto per evitare avanzamenti multipli consecutivi
      try { window.scrollTo({ top: 0, behavior: 'auto' }); } catch (e) {}
      // Aggiorna lo stato dei bottoni in nav coerentemente con la nuova pagina
      try {
        const iconsNav = document.getElementById('results-icons');
        if (iconsNav) {
          const btn = iconsNav.querySelector(`button[data-page="${next}"]`);
          if (btn) { btn.focus(); }
        }
      } catch (e) {}
      setTimeout(() => { lock = false; }, 500);
    } catch (e) {}
  };

  window.addEventListener('scroll', handler, { passive: true });
}

// Osservatore di fine pagina: avanza quando il fondo della pagina attiva è visibile
function initAutoAdvanceObserver() {
  // Disattivato su richiesta: nessun avanzamento automatico via observer
  return;
  try {
    if (window.__AUTO_ADVANCE_OBSERVER__) return;
    let lock = false;
    const sentinelId = 'auto-advance-sentinel';

    const ensureSentinelOnActivePage = () => {
      try {
        const current = getCurrentActivePage();
        if (!current) return;
        const container = document.getElementById(`page-${current}`);
        if (!container) return;
        // Evita attivazioni su pagine troppo corte (non ha senso auto-avanzare)
        try {
          const ch = container.scrollHeight;
          if (ch && ch <= window.innerHeight + 120) return;
        } catch (e) {}
        let sentinel = document.getElementById(sentinelId);
        if (!sentinel) {
          sentinel = document.createElement('div');
          sentinel.id = sentinelId;
          sentinel.style.width = '1px';
          sentinel.style.height = '1px';
        }
        // Assicura che il sentinel sia alla fine della pagina attiva
        if (sentinel.parentNode !== container) {
          try { sentinel.remove(); } catch (e) {}
          container.appendChild(sentinel);
        }
      } catch (e) {}
    };

  const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        if (lock) return;
        lock = true;
        try {
          const current = getCurrentActivePage();
          // Non auto-avanzare dalla pagina Intro: serve azione esplicita dell'utente
          if (current === 'intro') { lock = false; return; }
          const next = getNextPage(current);
          if (!next) { lock = false; return; }
          // Ulteriore guard: avanza solo se la pagina attiva ha contenuto oltre la viewport
          try {
            const active = document.getElementById(`page-${current}`);
            if (active && active.scrollHeight <= window.innerHeight + 120) { lock = false; return; }
          } catch (e) {}
          showResultsPage(next);
          // reset scroll in alto per evitare trigger multipli
          try { window.scrollTo({ top: 0, behavior: 'auto' }); } catch (e) {}
          // riposiziona il sentinel sulla nuova pagina attiva
          setTimeout(() => {
            ensureSentinelOnActivePage();
            const s = document.getElementById(sentinelId);
            if (s) observer.observe(s);
            lock = false;
          }, 200);
        } catch (e) { lock = false; }
      });
    }, { root: null, rootMargin: '0px', threshold: 0.99 });

    // rende disponibile globalmente per evitare duplicazioni
    window.__AUTO_ADVANCE_OBSERVER__ = observer;
    // posiziona e osserva il sentinel iniziale
    ensureSentinelOnActivePage();
    const sentinel = document.getElementById(sentinelId);
    if (sentinel) observer.observe(sentinel);
  } catch (e) {}
}

// Inizializza l'avanzamento sequenziale a fine pagina (scroll + observer)
function initSequentialScrollPageSwitch(options = {}) {
  try {
    if (window.__SEQUENTIAL_SCROLL_INIT__) return;
    window.__SEQUENTIAL_SCROLL_INIT__ = true;
  } catch (e) {}

  // Avanzamento via IntersectionObserver (robusto anche con contenuti variabili)
  try { if (typeof initAutoAdvanceObserver === 'function') initAutoAdvanceObserver(); } catch (e) {}

  // Fallback: avanzamento via scroll al fondo della pagina
  try { initScrollBottomPageSwitch(undefined, options); } catch (e) {}
}

// Attiva il cambio pagina quando si raggiunge il fondo della pagina
function initScrollBottomPageSwitch(nextPage = undefined, options) {
  // Disattivato su richiesta: nessun avanzamento automatico via scroll al fondo
  return;
  try {
    if (window.__AUTO_ADVANCE_SCROLL_BOTTOM__) return;
    window.__AUTO_ADVANCE_SCROLL_BOTTOM__ = true;
  } catch (e) {}

  const threshold = options && typeof options.threshold === 'number' ? options.threshold : 0; // px dal fondo
  let lock = false;

  const handler = () => {
    try {
      const resultsSection = document.getElementById('results-section');
      if (!resultsSection || resultsSection.classList.contains('hidden')) return;

      const doc = document.documentElement;
      const atBottom = (window.scrollY + window.innerHeight) >= (doc.scrollHeight - threshold);
      if (!atBottom || lock) return;

      // Evita auto-avanzamento dalla pagina Intro: richiede azione esplicita
      try {
        const current = getCurrentActivePage();
        if (current === 'intro') return;
      } catch (e) {}

      lock = true;
      // Determina la prossima pagina: se non specificata, usa l'ordine sequenziale
      let target = nextPage;
      try {
        if (!target) {
          const current = getCurrentActivePage();
          target = getNextPage(current);
        }
      } catch (e) {}
      if (!target) { lock = false; return; }

      // Cambia pagina risultati
      try { showResultsPage(target); } catch (e) {}

      // Se si passa alla Mappa, assicurati che il wrapper sia visibile
      try {
        if (target === 'map') {
          const mapWrapper = document.getElementById('map-wrapper');
          if (mapWrapper) mapWrapper.classList.remove('hidden');
        }
      } catch (e) {}

      // Reset scroll in alto per evitare trigger multipli consecutivi
      try { window.scrollTo({ top: 0, behavior: 'auto' }); } catch (e) {}

      // Rilascia il lock dopo breve timeout
      setTimeout(() => { lock = false; }, 400);
    } catch (e) {}
  };

  window.addEventListener('scroll', handler, { passive: true });
}

function buildItineraryPayload() {
  const sel = Array.isArray(manualSelection) ? manualSelection : [];
  const city = currentLocation || '';
  const locali = sel.map(a => ({
    name: a.name || '',
    address: a.address || a.formatted_address || '',
    type: a.type || 'ristorante',
    place_id: a.place_id || '',
    // Invia coordinate e immagine per persistenza lato backend
    lat: (a.location && typeof a.location.lat !== 'undefined') ? a.location.lat : (typeof a.lat !== 'undefined' ? a.lat : null),
    lng: (a.location && typeof a.location.lng !== 'undefined') ? a.location.lng : (typeof a.lng !== 'undefined' ? a.lng : null),
    image: a.image || a.photo || ''
  }));
  // Pagina 1 (piatti tipici): salva l'HTML generato come stringa JSON
  let page1_html = '';
  try {
    const el = document.querySelector('#page-intro .content-response');
    if (el) page1_html = el.innerHTML || '';
  } catch (e) {}
  // Pagina 3 (altri suggerimenti): salva l'oggetto dei risultati categorizzati
  let page3_ranked = {};
  try {
    if (window.lastRankedResults && typeof window.lastRankedResults === 'object') {
      const raw = window.lastRankedResults || {};
      const filtered = {};
      Object.keys(raw).forEach((category) => {
        const lower = (category || '').toLowerCase();
        // Normalizza: sostituisci underscore e spazi multipli con singolo spazio
        const norm = lower.replace(/[_\s]+/g, ' ').trim();
        // Escludi esplicitamente la pagina 2: "La nostra selezione" in tutte le varianti
        if (norm.includes('la nostra selezione')) return;
        // Categorie consentite/target per la terza pagina (inclusi sinonimi comuni)
        const allowed = [
          'hotel',
          'strutture ricettive',
          'cucina tipica',
          'ristoranti',
          'vini',
          'enoteca',
          'cantina',
          'cantine'
        ];
        const isThirdPageCat = allowed.some(a => norm.includes(a));
        if (isThirdPageCat) filtered[category] = raw[category];
      });
      page3_ranked = filtered;
    }
  } catch (e) {}
  // Pagina 3 (strutturato): usa ranked per i risultati categorizzati
  const ranked = page3_ranked;
  // Pagina 3 (La nostra selezione): salva anche l'HTML del pannello come stringa
  let selection_html = '';
  try {
    const panel = document.querySelector('#page-selection .our-selection');
    if (panel) {
      selection_html = panel.outerHTML || panel.innerHTML || '';
    }
  } catch (e) {}
  console.log("buildItineraryPayload -> city:", city, "num_locali:", sel.length, "locali:", locali);
  return { city, num_locali: sel.length, locali, page1_html, page3_ranked, ranked, selection_html };
}

function handleAutoSaveAfterLogin() {
  try {
    const url = new URL(window.location.href);
    const autosalva = url.searchParams.get('autosalva');
    const shouldFlag = (sessionStorage.getItem('save_after_login') === '1');
    console.log('DEBUG: handleAutoSaveAfterLogin called, autosalva=', autosalva, 'shouldFlag=', shouldFlag);
    console.log('DEBUG: current URL=', window.location.href);
    if (autosalva === '1' || shouldFlag) {
      const should = sessionStorage.getItem('save_after_login') === '1';
      const payloadStr = sessionStorage.getItem('pending_itinerary_payload');
      console.log('DEBUG: should save=', should, 'payload exists=', !!payloadStr);
      if (should && payloadStr) {
        fetch('/api/auth_status').then(r=>r.json()).then(js=>{
          console.log('DEBUG: auth status=', js);
          if (js.authenticated) {
            // Salva automaticamente l'itinerario dopo il login
            const payload = JSON.parse(payloadStr);
            console.log('DEBUG: saving payload=', payload);
            fetch('/api/save_itinerary', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload)
            })
            .then(r => r.json())
            .then(resp => {
              console.log('DEBUG: save response=', resp);
              // Rimuovi i dati da sessionStorage
              sessionStorage.removeItem('save_after_login');
              sessionStorage.removeItem('pending_itinerary_payload');
              
              if (resp && resp.success) {
                // Reindirizza all'area riservata dopo il salvataggio
                window.location.href = '/area_riservata';
              } else {
                alert('Errore nel salvataggio automatico dell\'itinerario: ' + (resp.error || 'Errore sconosciuto'));
                window.location.href = '/area_riservata';
              }
            })
            .catch(err => {
              console.error('Errore di rete nel salvataggio automatico:', err);
              sessionStorage.removeItem('save_after_login');
              sessionStorage.removeItem('pending_itinerary_payload');
              alert('Errore di rete nel salvataggio automatico dell\'itinerario');
              window.location.href = '/area_riservata';
            });
          } else {
            console.log('DEBUG: user not authenticated');
          }
        });
      } else {
        console.log('DEBUG: missing conditions for auto-save');
      }
    }
  } catch (e) {
    console.error('DEBUG: error in handleAutoSaveAfterLogin:', e);
  }
}

// Attiva l'autosalvataggio dopo login quando la pagina è pronta
document.addEventListener('DOMContentLoaded', () => {
  // Aggiorna la visibilità del bottone di salvataggio all'avvio
  updateSaveItineraryButtonVisibility();
});

// Aggiorna la visibilità del bottone di salvataggio in base alle selezioni
function updateSaveItineraryButtonVisibility() {
  const saveContainer = document.getElementById('save-itinerary-container');
  if (!saveContainer) return;
  
  const payload = buildItineraryPayload();
  const selectionCount = payload.locali ? payload.locali.length : 0;
  const currentPage = (typeof getCurrentActivePage === 'function') ? getCurrentActivePage() : null;
  const onSelection = currentPage === 'selection';
  const shouldShow = onSelection && selectionCount > 0;
  saveContainer.classList.toggle('hidden', !shouldShow);
  if (shouldShow) {
    const saveBtn = document.getElementById('save-itinerary-btn');
    if (saveBtn) saveBtn.textContent = `salva itinerario (${selectionCount})`;
  }
}

function attachSaveItineraryHandlers() {
  const buttons = document.querySelectorAll('#save-itinerary-btn');

  buttons.forEach(btn => {
    if (btn.dataset.bound === '1') return;
    btn.dataset.bound = '1';

    btn.addEventListener('click', () => {

      // 1️⃣ Costruisci SEMPRE il payload (anche se non loggato)
      const payload = buildItineraryPayload();

      // 🔍 Controlla se ci sono selezioni
      if (!payload.locali || payload.locali.length === 0) {
        alert('Per salvare un itinerario, devi prima selezionare almeno un locale dalla mappa o dai risultati di ricerca.');
        return;
      }

      // 2️⃣ Verifica autenticazione
      fetch('/api/auth_status')
        .then(r => r.json())
        .then(js => {

          // 3️⃣ Se NON loggato → salvataggio locale + redirect login
          if (!js.authenticated) {

            // Recupera l'ultimo messaggio utente e salvalo
            try {
              let lastUser = null;
              for (let i = messageHistory.length - 1; i >= 0; i--) {
                const m = messageHistory[i];
                if (m.role === 'user' && m.parts && m.parts[0] && m.parts[0].text) {
                  lastUser = m.parts[0].text;
                  break;
                }
              }
              if (lastUser) {
                sessionStorage.setItem('pending_search', lastUser);
              }

              // salva gli stati
              sessionStorage.setItem('return_to_selection', '1');
              sessionStorage.setItem('pending_itinerary_payload', JSON.stringify(payload));
              sessionStorage.setItem('save_after_login', '1');

              try { snapshotResults(); } catch (e) {}
            } catch (e) {}

            // Redireziona al login
            const target = '/login?next=' + encodeURIComponent('/area_riservata?autosalva=1');
            window.location.href = target;
            return;
          }

          // 4️⃣ Se è loggato → salva davvero
          fetch('/api/save_itinerary', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          })
            .then(r => r.json())
            .then(resp => {
              if (resp && resp.success) {
                try { snapshotResults(); } catch (e) {}
                alert('Itinerario salvato con successo! Verrai reindirizzato alla tua area riservata.');
                setTimeout(() => {
                  window.location.href = '/area_riservata';
                }, 1500);
                return;
              }

              alert('Errore nel salvataggio itinerario' + (resp && resp.error ? (': ' + resp.error) : ''));
            })
            .catch(() => {
              alert('Errore di rete nel salvataggio itinerario');
            });

        });
    });
  });
}

// Aggiorna un programma esistente
async function updateExistingProgram(programId) {
  try {
    const payload = buildItineraryPayload();
    // Includi anche i contenuti di pagina 1 e 3 nel body
    const body = JSON.stringify({
      program_id: programId,
      city: payload.city,
      num_locali: payload.num_locali,
      locali: payload.locali,
      page1_html: payload.page1_html || '',
      // usa page3_ranked (filtrato) oppure ranked come fallback
      page3_ranked: payload.page3_ranked || payload.ranked || {}
    });

    const auth = await fetch('/api/auth_status').then(r => r.json()).catch(() => ({ authenticated: false }));
    if (!auth.authenticated) {
      alert('Devi essere autenticato per aggiornare il programma');
      return;
    }

    const resp = await fetch('/api/update_program', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body
    }).then(r => r.json());

    if (resp && resp.success) {
      alert('Programma aggiornato correttamente');
      // Ricarica i dettagli dal backend per riflettere l’update
      try {
        const pid = programId || (window.__RESTORE_PROGRAM_ID__ || getProgramIdFromPath());
        if (pid) {
          await loadProgramFromBackend(pid);
        }
      } catch (e) {}
    } else {
      alert('Errore nell’aggiornamento del programma' + (resp && resp.error ? (': ' + resp.error) : ''));
    }
  } catch (e) {
    alert('Errore di rete durante update programma');
  }
}

// Bind opzionale: se esiste un bottone con id #update-itinerary-btn lo aggancia
document.addEventListener('DOMContentLoaded', () => {
  try {
    const btn = document.getElementById('update-itinerary-btn');
    const pid = window.__RESTORE_PROGRAM_ID__ || getProgramIdFromPath();
    if (btn && pid) {
      if (btn.dataset.bound !== '1') {
        btn.dataset.bound = '1';
        btn.addEventListener('click', () => updateExistingProgram(pid));
      }
    }
  } catch (e) {}
  try {
    const menuBtn = document.getElementById('sidebar-menu-btn');
    const menuPanel = document.getElementById('sidebar-menu-panel');
  
  } catch (e) {}
});


function clearResultPages() {
    // Non cancellare la pagina Intro: preserva i contenuti dei Piatti Tipici
    const pages = ['selection','lfw','map'];
    pages.forEach(p => {
        const el = document.getElementById(`page-${p}`);
        if (el) el.innerHTML = '';
    });
}


function ensureLfwStandardSections(toolData) {
  const pageLfw = document.getElementById('page-lfw');
  if (!pageLfw) return;
  // Assicura etichetta "Altri suggerimenti" presente in alto a sinistra
  let label = document.getElementById('lfw-left-label');
  if (!label) {
    label = document.createElement('div');
    label.id = 'lfw-left-label';
    label.className = 'text-emerald-600 font-semibold text-lg ml-6 mt-2';
    label.textContent = 'Altri suggerimenti';
    pageLfw.insertBefore(label, pageLfw.firstChild);
  }
  // Allinea tutte le intestazioni della pagina LFW a sinistra e in alto
  const headings = pageLfw.querySelectorAll('h3');
  headings.forEach(h => {
    h.classList.remove('justify-center');
    h.classList.add('justify-start');
    h.classList.add('text-left');
  });
  // Sposta le sezioni verso l'alto e allinea a sinistra
  const sections = pageLfw.querySelectorAll('.mb-8');
  sections.forEach(sec => {
    // Rimuove eventuali margin-top e centra a sinistra
    try { sec.style.marginTop = '8px'; } catch(e) {}
    if (!sec.classList.contains('ml-6')) sec.classList.add('ml-6');
  });
  // Assicura la presenza della griglia Suggerimenti
  try { ensureSuggestionsGrid(); } catch (e) {}
  // Popola l'array suggests dai contenuti LFW (senza duplicare la UI)
  try { collectLfwSuggestions(); } catch (e) {}
}

// Helper: sposta l'unico form di ricerca nello slot indicato
function moveSearchFormToSlot(slotId) {
  try {
    const form = document.getElementById('search-form');
    const slot = document.getElementById(slotId);
    if (!form || !slot) return;
    if (form.parentElement !== slot) {
      slot.appendChild(form);
      try { form.classList.add('w-full'); } catch (e) {}
    }
  } catch (e) {
    console.warn('moveSearchFormToSlot error:', e);
  }
}

let currentSearchController;
const searchFormEl = document.getElementById('search-form');
if (searchFormEl) {
searchFormEl.addEventListener('submit', async (event) => {
  event.preventDefault();
  try { window.__SUPPRESS_HOME_OVERLAY__ = false; } catch (e) {}
  // Ripulisci flag di navigazione forzata per evitare switch indesiderati
  try { sessionStorage.removeItem('return_to_selection'); } catch (e) {}
  try { sessionStorage.removeItem('save_after_login'); } catch (e) {}
  const searchInput = document.getElementById('search-input');
  // Usa il termine passato nell'evento o quello dall'input
  const searchTerm = event.searchTerm || searchInput.value;
  const resultsContainer = document.getElementById('results-container');
  const mapContainer = document.getElementById('map-container');
  const categorizedContainer = document.getElementById('categorized-results-container');

  if (searchTerm.trim() === '') {
    resultsContainer.innerHTML = '<p class="text-slate-600 text-center">Inserisci un termine di ricerca.</p>';
    return;
  }
  
  // Pulisci immediatamente la barra di ricerca dopo aver salvato il termine
  searchInput.value = '';
  
  // PULIZIA PREVENTIVA CONDIZIONALE PRIMA DI INIZIARE UNA NUOVA RICERCA
  console.log('🧹 PULIZIA PREVENTIVA: Verificando se pulire il contenuto...');
  
  // Rileva se siamo nella pagina Programma (Selezione/LFW/Mappa o URL /program/:id)
  const isProgramPage = !!document.getElementById('page-selection')
    || !!document.getElementById('page-lfw')
    || !!document.getElementById('page-map')
    || !!window.__RESTORE_PROGRAM_ID__
    || (typeof getProgramIdFromPath === 'function' && !!getProgramIdFromPath());
  
  // Non cancellare le pagine dei risultati quando la chat è attiva o siamo in Programma
  if (!chatbotModeActive && !isProgramPage) {
    clearResultPages();
  } else {
    console.log('🔒 Pagine risultati preservate (chat attiva o Programma)');
  }
  // 1. Pulisci i contenitori quando viene premuto Invio, ma solo se non siamo in modalità chatbot o Programma
  console.log('🧹 Verificando se pulire i contenitori...');
  const detectedLocationCandidate = extractLocationFromQuery(searchTerm);
  const isNewLocation = !!(detectedLocationCandidate && detectedLocationCandidate.toLowerCase() !== String(currentLocation || '').toLowerCase());
  const allContainers = [
    'results-container',
    
    'categorized-results-container'
  ];
  
  allContainers.forEach(containerId => {
    const container = document.getElementById(containerId);
    if (container) {
      // Se siamo in modalità chatbot o Programma, mantieni i contenitori e il loro contenuto
      if ((!chatbotModeActive && !isProgramPage) || isNewLocation) {
        
        container.innerHTML = '';
        console.log(`🗑️ Svuotato contenitore: ${containerId}`);
      } else {
        console.log(`🔒 Mantenuto contenuto del contenitore: ${containerId} (chat attiva o Programma)`);
      }
      // Non nascondere i contenitori, solo svuotarli se necessario
      container.style.display = 'block';
    
  }
  });
  
  

  
  // 2. Nascondi tutti gli elementi di interfaccia
  const elementsToHide = [
    'results-title',
    'loading-status'
  ];
  
  elementsToHide.forEach(elementId => {
    const element = document.getElementById(elementId);
    if (element) {
      element.style.display = 'none';
      element.innerHTML = '';
    }
  });
  
  // 3. Reset delle variabili globali
  // Non resettare messageHistory per mantenere la cronologia della conversazione
  // Non resettare chatbotModeActive qui per mantenere la modalità chatbot attiva
  
  // 4. Rimuovi classi CSS dinamiche
  document.body.className = document.body.className.replace(/\s*(chatbot-active|search-active|results-visible)\s*/g, '');
  
  console.log('✅ PULIZIA PREVENTIVA COMPLETATA');

  // Sposta subito il form nello slot risultati (a destra) dopo l'invio dalla Home
    try { moveSearchFormToSlot('results-form-slot'); } catch (e) { console.warn('moveSearchFormToSlot on submit error:', e); }

  // Ripristina le classi di griglia originali per il results-container
  resultsContainer.className = 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-8';

  // Flag per evitare contenuti duplicati durante questa ricerca
  let contentInsertedForThisSearch = false;
  
  // DEBUG: Stato iniziale della località
  console.log('🔍 DEBUG - Stato iniziale currentLocation:', currentLocation);
  console.log('🔍 DEBUG - searchTerm ricevuto:', searchTerm);
    console.log('🔍 DEBUG - chatbotModeActive:', chatbotModeActive);
  
  // Estrai e memorizza la località dalla query se presente
  const previousLocation = currentLocation;
  const detectedLocation = extractLocationFromQuery(searchTerm);

  // Se l'utente chiede di visitare una città diversa, mantieni visibile la chat
  // e mostra il messaggio richiesto, evitando il riquadro verde
  if (detectedLocation && detectedLocation.toLowerCase() !== String(previousLocation || '').toLowerCase()) {
    // Attiva modalità chatbot per non mostrare l'overlay di caricamento
    chatbotModeActive = true;
    // Sopprimi esplicitamente l'overlay Home per questo cambio città
    try { window.__SUPPRESS_HOME_OVERLAY__ = true; } catch (e) {}
    // Mantieni la chat visibile
    try { window.__CHAT_TOGGLE_VISIBLE__ = true; } catch (e) {}
    try { updateChatPanelVisibility(); } catch (e) {}
    // Messaggio informativo delegato al flusso streaming
  }
  if (detectedLocation) {
    currentLocation = detectedLocation;
    localStorage.setItem('sitesense_current_location', currentLocation);
    console.log('🗺️ Località corrente aggiornata a:', currentLocation);
       resultsContainer.innerHTML = '';
       categorizedContainer.innerHTML = '';       
      



  } else {
    console.log('🔍 DEBUG - Nessuna località rilevata nella query, mantengo currentLocation:', currentLocation);
  }

  // Se abbiamo una località memorizzata e non è già presente nella query, non modificare la query utente
  // Se le chiavi Maps non sono valide, carica contenuti dalla cache per la città
  try { await maybeLoadCityCacheFallback(); } catch (e) { console.warn('Fallback cache città non riuscito:', e); }
  
  
  // Aggiungi il messaggio utente alla history
  // Se siamo in modalità chatbot, manteniamo la cronologia esistente
  // Se non siamo in modalità chatbot, resettiamo la cronologia prima di aggiungere il nuovo messaggio
  if (!chatbotModeActive) {
    messageHistory = [];
  }
  messageHistory.push({ role: 'user', parts: [{ text: searchTerm }] });


  try { chatbotModeActive = true; } catch (e) {}
  try { window.__CHAT_TOGGLE_VISIBLE__ = true; updateChatPanelVisibility(); } catch (e) {}
  try { addChatbotMessage(searchTerm, true); addTypingIndicator(); } catch (e) {}

  
  // Rileva se siamo nella pagina Programma (Results Section visibile)
  const resultsSection = document.getElementById('results-section');
  const isResultsVisible = resultsSection && resultsSection.offsetParent !== null;

  const isProgramPageLocal = isResultsVisible
    || !!window.__RESTORE_PROGRAM_ID__
    || (typeof getProgramIdFromPath === 'function' && !!getProgramIdFromPath());
  const isProgramMode = isProgramPageLocal || (typeof window.programMode !== 'undefined' && window.programMode);

  if (isProgramMode) {
     console.log('🔒 Animazione di caricamento non mostrata (Program Mode attivo)');
     try { window.__FIRST_SEARCH_DONE__ = true; } catch (e) {}
  } else {
     // Home / Results Mode: Mostra SEMPRE l'animazione (anche se chat attiva)
     showAILoadingAnimation(searchTerm);
     try { window.__FIRST_SEARCH_DONE__ = true; } catch (e) {}
  } 

  try {
    if (currentSearchController) { try { currentSearchController.abort(); } catch (e) {} }
    currentSearchController = new AbortController();
    const response = await fetch('/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query: searchTerm, history: messageHistory }),
      signal: currentSearchController.signal,
    });

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      
      buffer += decoder.decode(value, { stream: true });
      
      // Processa ogni riga JSON nel buffer
      let end = buffer.indexOf('\n');
      while (end !== -1) {
        let jsonString = buffer.substring(0, end).trim();
        
        if (jsonString) {
          // Rimuovi il prefisso 'data: ' se presente
          if (jsonString.startsWith('data: ')) {
            jsonString = jsonString.substring(6); // Rimuovi 'data: '
          }
          
          try {
            const data = JSON.parse(jsonString);
            console.log('📨 DATI RICEVUTI DAL SERVER:', data);
            
            if (data.type === 'reload_page') {
              console.log('🔄 RICEVUTO SEGNALE reload_page:', data);
              
              // ELIMINAZIONE COMPLETA E IMMEDIATA DI TUTTO IL CONTENUTO VECCHIO SOLO SE NON SIAMO IN MODALITÀ CHATBOT
              console.log('🧹 ELIMINAZIONE CONDIZIONALE DEL CONTENUTO VECCHIO...');
              
              // Ferma immediatamente qualsiasi processo in corso
              hideAILoadingAnimation();
              
              // Pulisci e nascondi i contenitori dei risultati (NON il chatbot)
              const containers = [
                'results-container',
                'map-container', 
                'categorized-results-container',
                'results-title',
                'loading-status'
              ];
              
              containers.forEach(containerId => {
                const container = document.getElementById(containerId);
                if (container) {
                  // Se siamo in modalità chatbot, mantieni i contenitori e il loro contenuto
                  if (chatbotModeActive) {
                    // Mantieni il contenuto e rendi visibili i contenitori
                    container.style.display = 'block';
                    container.style.visibility = 'visible';
                    container.style.opacity = '1';
                  } else {
                    // Solo se non siamo in modalità chatbot, svuota i contenitori
                    container.innerHTML = '';
                    container.style.display = 'none';
                    container.style.visibility = 'hidden';
                    container.style.opacity = '0';
                  }
                }
              });
              
              // Reset delle variabili globali, ma mantieni la cronologia se in modalità chatbot
              if (!chatbotModeActive) {
                messageHistory = [];
              }

              
              // Rimuovi TUTTE le classi CSS dinamiche
              document.body.classList.remove('chatbot-active', 'results-visible');
              document.body.className = document.body.className.replace(/\b(search|loading|results)\S*/g, '');
              
              // Pulisci anche eventuali elementi dinamici creati
              const dynamicElements = document.querySelectorAll('.dynamic-content, .ai-generated, .search-result');
              dynamicElements.forEach(el => el.remove());
              
              console.log('✅ CONTENUTO VECCHIO COMPLETAMENTE ELIMINATO');
              
              // Ora avvia la nuova ricerca se c'è un messaggio
              if (data.user_message) {
                console.log('🚀 AVVIO NUOVA RICERCA CON:', data.user_message);
                manualSelection.remove
                // Estrai e aggiorna la località se presente nel nuovo messaggio
                const detectedLocation = extractLocationFromQuery(data.user_message);
                if (detectedLocation) {
                  currentLocation = detectedLocation;
                  localStorage.setItem('sitesense_current_location', currentLocation);
                  console.log('🗺️ Località corrente aggiornata durante reload a:', currentLocation);
                }
                 resultsContainer.innerHTML = '';
                 mapContainer.innerHTML = '';
                categorizedContainer.innerHTML = ''; 
                container.innerHTML = '';
                // Usa il messaggio originale senza aggiungere località precedente
                const searchInput = document.getElementById('search-input');
                if (searchInput) {
                  // Non rimettere il valore nella barra di ricerca, mantienila pulita
                  // Avvia immediatamente la nuova ricerca
                  setTimeout(() => {
                    console.log('📤 INVIO FORM PER NUOVA RICERCA con messaggio originale:', data.user_message);
                    // Simula l'invio del form con il messaggio originale
                    const event = new Event('submit');
                    event.searchTerm = data.user_message; // Passa il termine originale
                    document.getElementById('search-form').dispatchEvent(event);
                  }, 50); // Ridotto il timeout per essere più immediato
                }
              }
              
              return; // Interrompi l'esecuzione per evitare elaborazione di altri dati
            }
            if (data.error) {
              hideAILoadingAnimation();
              const resultsContainer = document.getElementById('results-container');
              if (resultsContainer) {
                resultsContainer.innerHTML = `<p class="text-red-500">${data.error}</p>`;
              }
            }
            if (data.complete_html && !contentInsertedForThisSearch) {
              processAndDisplayContent({ answer: data.complete_html });
              contentInsertedForThisSearch = true;
            }
            if (data.answer && !contentInsertedForThisSearch) {
              processAndDisplayContent({ answer: data.answer });
              contentInsertedForThisSearch = true;
            }
            if (data.status) {
              const loadingStatus = document.getElementById('loading-status');
              if (loadingStatus) {
                loadingStatus.textContent = data.status;
                // Ripristina la visibilità del loading status
                loadingStatus.style.display = 'block';
                loadingStatus.style.visibility = 'visible';
                loadingStatus.style.opacity = '1';
              } else {
                // Se l'elemento loading-status non esiste, potrebbe essere dentro l'animazione AI
                // Cerca all'interno del container dell'animazione
                const aiLoadingStatus = document.querySelector('#categorized-results-container #loading-status');
                if (aiLoadingStatus) {
                  aiLoadingStatus.textContent = data.status;
                  aiLoadingStatus.style.display = 'block';
                  aiLoadingStatus.style.visibility = 'visible';
                  aiLoadingStatus.style.opacity = '1';
                }
              }
              // Aggiorna la località se il backend la segnala
              if (data.detected_location) {
                currentLocation = data.detected_location;
               
                if (resultsContainer) resultsContainer.innerHTML = '';
                if (mapContainer) mapContainer.innerHTML = '';
                 if (categorizedContainer) categorizedContainer.innerHTML = '';
                try { localStorage.setItem('sitesense_current_location', currentLocation); } catch (e) {}
                console.log('📍 Località impostata dal backend:', currentLocation);
              }
            }
            if (data.content_payload && !contentInsertedForThisSearch) {
              processAndDisplayContent(data.content_payload);
              contentInsertedForThisSearch = true;
            }
            if (data.map_payload) {
              processAndDisplayMap(data.map_payload);
            }
            if (data.tool_name && data.tool_data) {
              processAndDisplayMap({ tool_name: data.tool_name, tool_data: data.tool_data });
            }
            if (data.chatbot_message) {
              if (data.chatbot_message.isUser) {
                // Messaggio dell'utente: aggiungi il messaggio e poi l'indicatore di digitazione
                addChatbotMessage(data.chatbot_message.message, true);
                addTypingIndicator();
              } else {
                // Risposta del bot: rimuovi l'indicatore e aggiungi la risposta
                addChatbotMessage(data.chatbot_message.message, false);
              }
            }
            if (data.chatbot_mode_activated && !data.force_new_search) {
              // Attiva la modalità chatbot per le ricerche successive
              // ma solo se non è stata richiesta una nuova ricerca forzata
              chatbotModeActive = true;
              console.log('Modalità chatbot attivata');
              
              // Aggiorna visibilità del pannello chat in modo condizionato
              updateChatPanelVisibility();
            }
            
            // Aggiorna la località se inviata dal backend (sempre, indipendentemente da status)
            if (data.detected_location) {
              currentLocation = data.detected_location;
              try { window.detectedLocation = currentLocation; localStorage.setItem('sitesense_current_location', currentLocation); } catch (e) {}
              console.log('📍 Località impostata dal backend:', currentLocation);
            }
            
            // Assicurati che il pannello chat sia visibile quando arrivano messaggi
            
          } catch (e) {
            console.error('Error parsing JSON:', e, jsonString);
          }
        }

        // Rimuovi il blocco JSON processato dal buffer
        buffer = buffer.substring(end + 1);
        end = buffer.indexOf('\n');
      }
    }
    // Processa eventuali dati residui nel buffer (senza newline finale)
    if (buffer && buffer.trim()) {
      let jsonString = buffer.trim();
      if (jsonString.startsWith('data: ')) {
        jsonString = jsonString.substring(6);
      }
      try {
        const data = JSON.parse(jsonString);
        console.log('📨 DATI FINALI DAL SERVER:', data);
        if (data.error) {
          const resultsContainer = document.getElementById('results-container');
          if (resultsContainer) {
            resultsContainer.innerHTML = `<p class="text-red-500">${data.error}</p>`;
          }
        }
        if (data.complete_html && !contentInsertedForThisSearch) {
          processAndDisplayContent({ answer: data.complete_html });
          contentInsertedForThisSearch = true;
        }
        if (data.answer && !contentInsertedForThisSearch) {
          processAndDisplayContent({ answer: data.answer });
          contentInsertedForThisSearch = true;
        }
        if (data.content_payload && !contentInsertedForThisSearch) {
          processAndDisplayContent(data.content_payload);
          contentInsertedForThisSearch = true;
        }
        if (data.map_payload) {
          processAndDisplayMap(data.map_payload);
        }
        if (data.tool_name && data.tool_data) {
          processAndDisplayMap({ tool_name: data.tool_name, tool_data: data.tool_data });
        }
        // Aggiorna la località se il backend la invia nel blocco finale
        if (data.detected_location) {
          currentLocation = data.detected_location;
          try { localStorage.setItem('sitesense_current_location', currentLocation); } catch (e) {}
          console.log('📍 Località impostata dal backend (final chunk):', currentLocation);
        }
      } catch (e) {
        console.error('Errore parsing JSON finale:', e, jsonString);
      }
    }
    try { importBackendSelection(); } catch (e) { console.error('Errore importBackendSelection:', e); }
    hideAILoadingAnimation();
    currentSearchController = null;

  } catch (error) {
    if (error && error.name === 'AbortError') { return; }
    console.error('Fetch stream error:', error);
    hideAILoadingAnimation();
    resultsContainer.innerHTML = `<p class="text-red-500">Errore durante la comunicazione con il server.</p>`;
  }
});
}

// Trasforma il JSON di cache città nel formato atteso da processAndDisplayMap
function transformCityCacheToToolData(cache) {
  const toolData = {};
  const items = Array.isArray(cache.locals) ? cache.locals : [];
  const byCat = {};
  items.forEach((p) => {
    const rawCat = (p.category || '').toString().trim().toLowerCase();
    const cat = rawCat.replace(/[_\s]+/g, ' ');
    if (!byCat[cat]) byCat[cat] = [];
    byCat[cat].push({
      place_id: p.place_id || '',
      foto_url: p.image || '',
      nome: p.name || '',
      indirizzo: p.formatted_address || '',
      valutazione: p.rating || null
    });
  });
  Object.keys(byCat).forEach((cat) => {
    toolData[cat] = { results: byCat[cat] };
  });
  return toolData;
}

async function maybeLoadCityCacheFallback() {
  // Disabilitato: il caricamento della cache città avviene ora lato server
  return;
  try {
    const statusRes = await fetch('/api/maps_status');
    if (!statusRes.ok) return;
    const status = await statusRes.json();
    if (status && status.maps_key_ok) return; // chiave ok, nessun fallback
    const city = (currentLocation || '').trim();
    if (!city) return;
    const r = await fetch(`/api/load_city_cache?city=${encodeURIComponent(city)}`);
    if (!r.ok) return;
    const data = await r.json();
    const toolData = transformCityCacheToToolData(data);
    // Memorizza per pagina 3 e visualizza
    window.lastRankedResults = toolData;
    try { window.usedCityCacheFallback = true; } catch (e) {}
    processAndDisplayMap({ tool_name: 'search_google_maps', tool_data: toolData });
    // Mostra la pagina LFW come prima vista dei risultati
    try { showResultsPage('lfw'); } catch (e) {}
  } catch (e) {
    console.warn('maybeLoadCityCacheFallback error:', e);
  }
}

// Stato globale per evitare salvataggi duplicati nella stessa sessione
try {
  if (typeof window.cityCacheSavedForCurrentSession === 'undefined') window.cityCacheSavedForCurrentSession = false;
  if (typeof window.usedCityCacheFallback === 'undefined') window.usedCityCacheFallback = false;
  // Stato di autosalvataggio per città: salva quando cambia contenuto o città, con throttle
  if (typeof window.__cityCacheSaveState === 'undefined') {
    window.__cityCacheSaveState = { city: '', selectionCount: 0, suggestsCount: 0, lastSaveAt: 0 };
  }
} catch (e) {}

async function fetchMapsStatusOnce() {
  try {
    if (window.__mapsStatusCached) return window.__mapsStatusCached;
    const res = await fetch('/api/maps_status');
    if (!res.ok) return null;
    const s = await res.json();
    window.__mapsStatusCached = s;
    return s;
  } catch (e) {
    return null;
  }
}
function buildCityCachePayload() {
  const fromLocalStorage = (() => { try { return (localStorage.getItem('sitesense_current_location') || '').trim(); } catch (_) { return ''; } })();
  const cityName = (typeof currentLocation === 'string' && currentLocation.trim())
    ? currentLocation.trim()
    : ((window.detectedLocation || fromLocalStorage || '').trim());
  const ranked = (typeof window.lastRankedResults === 'object' && window.lastRankedResults) ? window.lastRankedResults : {};
  const manual = Array.isArray(manualSelection) ? manualSelection : [];
  const sugg = Array.isArray(suggests) ? suggests : [];

  const locals = [];
  const locals_selection = [];
  const locals_suggests = [];

  const normalize = (p, categoryHint = '') => {
    if (!p) return null;
    const loc = (p.location && typeof p.location === 'object') ? p.location : {};
    return {
      place_id: p.place_id || p.id || '',
      name: p.name || p.nome || '',
      formatted_address: p.formatted_address || p.indirizzo || p.address || '',
      image: p.image || p.photo || p.foto_url || '',
      category: p.category || categoryHint || '',
      lat: (typeof p.lat !== 'undefined') ? p.lat : (typeof loc.lat !== 'undefined' ? loc.lat : null),
      lng: (typeof p.lng !== 'undefined') ? p.lng : (typeof loc.lng !== 'undefined' ? loc.lng : null),
      rating: (typeof p.rating !== 'undefined') ? p.rating : (typeof p.valutazione !== 'undefined' ? p.valutazione : null),
      reviews_count: (typeof p.reviews !== 'undefined') ? p.reviews : (typeof p.user_ratings_total !== 'undefined' ? p.user_ratings_total : null)
    };
  };

  try {
    // Ignora i risultati 'ranked' per il salvataggio: usiamo solo manualSelection e suggests
  } catch (e) {}

  try {
    manual.forEach(it => { const n = normalize(it, 'la_nostra_selezione'); if (n) { locals.push(n); locals_selection.push(n); } });
  } catch (e) {}

  try {
    sugg.forEach(it => { const n = normalize(it); if (n) { locals.push(n); locals_suggests.push(n); } });
  } catch (e) {}

  return { city: cityName, locals, locals_selection, locals_suggests };
}

async function maybeAutoSaveCityCache(source) {
  return; // disabilitato: il salvataggio avviene solo su click del pulsante
}

// Banner di feedback vicino alla toolbar salvataggio
function showSaveSearchFeedback(ok, message) {
  try {
    const container = document.getElementById('save-itinerary-container');
    if (!container) return;
    let feedback = document.getElementById('save-search-feedback');
    if (!feedback) {
      feedback = document.createElement('div');
      feedback.id = 'save-search-feedback';
      feedback.className = 'px-4 py-2 rounded-full shadow font-semibold text-sm';
      // Inserisci il messaggio come primo elemento per mantenerlo a sinistra dei bottoni
      container.insertBefore(feedback, container.firstChild);
    }
    feedback.textContent = message || (ok ? 'Ricerca salvata!' : 'Errore nel salvataggio');
    feedback.style.backgroundColor = ok ? '#b8f36d' : '#f87171'; // verde vs rosso
    feedback.style.color = '#0f3e34';
    feedback.style.display = '';
    try { if (feedback._hideTimer) clearTimeout(feedback._hideTimer); } catch (_) {}
    feedback._hideTimer = setTimeout(() => { try { feedback.style.display = 'none'; } catch (_) {} }, 3000);
  } catch (_) {}
}

// Salvataggio diretto della cache città (senza filtri/throttle)
async function saveCityCacheNow() {
  try {
    const payload = buildCityCachePayload();
    if (!payload || !payload.city) {
      console.warn('Salvataggio diretto: payload non valido o città assente');
      showSaveSearchFeedback(false, 'Dati mancanti: selezione o città assente');
      return { ok: false, message: 'Dati mancanti' };
    }
    const resp = await fetch('/api/save_city_cache', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (resp.ok) {
      try {
        const data = await resp.json();
        if (data && data.success) {
          console.info('Cache città salvata per', payload.city, '->', data.selection_path, data.suggests_path);
          showSaveSearchFeedback(true, 'Ricerca salvata!');
          return { ok: true, message: 'Ricerca salvata!' };
        } else {
          console.info('Cache città: risposta OK ma struttura inattesa', data);
          showSaveSearchFeedback(true, 'Ricerca salvata.');
          return { ok: true, message: 'Ricerca salvata.' };
        }
      } catch (_) {
        console.info('Cache città salvata manualmente per', payload.city);
        showSaveSearchFeedback(true, 'Ricerca salvata.');
        return { ok: true, message: 'Ricerca salvata.' };
      }
    } else {
      const txt = await resp.text();
      console.warn('Salvataggio diretto fallito:', resp.status, txt);
      showSaveSearchFeedback(false, 'Errore salvataggio. Riprovare.');
      return { ok: false, message: 'Errore salvataggio' };
    }
  } catch (e) {
    console.warn('saveCityCacheNow error:', e);
    showSaveSearchFeedback(false, 'Errore di rete. Riprovare.');
    return { ok: false, message: 'Errore di rete' };
  }
}



// Gestione del pulsante clear (null-safe)
const clearBtn = document.getElementById('clear-button');
if (clearBtn) {
  clearBtn.addEventListener('click', () => {
    const searchInput = document.getElementById('search-input');
    if (searchInput) { searchInput.value = ''; }
    // Rimosso focus() per evitare scroll automatico
  });
}

// Pulsante flottante "salva ricerca": salvataggio manuale
try {
  const saveSearchBtn = document.getElementById('save-search-btn');
  if (saveSearchBtn) {
    saveSearchBtn.addEventListener('click', async (e) => {
      try { if (e) { e.preventDefault(); e.stopPropagation(); } } catch (_) {}
      try { window.__USER_NAV_ACTIVE__ = true; } catch (e) {}
      try {
        // Invio diretto alla rotta /api/save_city_cache
        await saveCityCacheNow();
      } catch (e) {
        console.warn('Errore nel salvataggio manuale della ricerca:', e);
        try { showSaveSearchFeedback(false, 'Errore inatteso nel salvataggio'); } catch (_) {}
      }
    });
  }
} catch (e) {}

// Gestione dell'invio con Enter (senza Shift)
const searchInputEl = document.getElementById('search-input');
if (searchInputEl) {
searchInputEl.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    const formEl = document.getElementById('search-form');
    if (formEl) formEl.dispatchEvent(new Event('submit'));
  }
});
}

// Auto-focus sull'input quando la pagina si carica
document.addEventListener('DOMContentLoaded', () => {
	
  try {
    const urlParams = new URLSearchParams(window.location.search || '');
    if (urlParams.get('restore') === '1') {
      sessionStorage.setItem('restore_results', '1');
      chatbotModeActive = true;
    }
  } catch (e) {}
  // Reset delle variabili di sessione al caricamento della pagina solo se non in modalità chatbot
  if (!chatbotModeActive) {
    messageHistory = [];
  }
  // Non resettare chatbotModeActive al caricamento della pagina
  
  // Pulisci solo i contenitori dei risultati se non siamo in modalità chatbot, NON il chatbot
  const resultsContainer = document.getElementById('results-container');
  const mapContainer = document.getElementById('map-container');
  const categorizedContainer = document.getElementById('categorized-results-container');
  
  // Se non siamo in modalità chatbot, pulisci i contenitori
  if (!chatbotModeActive) {
    if (resultsContainer) resultsContainer.innerHTML = '';
    if (mapContainer) mapContainer.innerHTML = '';
    if (categorizedContainer) categorizedContainer.innerHTML = '';
    console.log('🧹 Contenitori puliti al caricamento della pagina');
    // Mantieni solo la homepage (hero) visibile
    const resultsSection = document.getElementById('results-section');
    if (resultsSection) resultsSection.classList.add('hidden');
    const mapWrapper = document.getElementById('map-wrapper');
    if (mapWrapper) mapWrapper.classList.add('hidden');
    const chatRightPanel = document.getElementById('chat-right-panel');
    if (chatRightPanel) chatRightPanel.classList.add('hidden');
  } else {
    console.log('🔒 Contenuto dei contenitori mantenuto (modalità chatbot attiva)');
  }

  // Inizializza osservatore per reagire ai cambi dinamici nelle sezioni dei risultati
  try { initResultsMutationObserver(); } catch (e) {}
  try { attachSaveItineraryHandlers(); } catch (e) {}
  
  // NON pulire il chatbot-messages per preservare la cronologia
  
  const searchInput = document.getElementById('search-input');
  
  // Controlla se c'è un messaggio in attesa dal sessionStorage
  const pendingSearch = sessionStorage.getItem('pending_search');
  if (pendingSearch) {
    console.log('🔄 Trovato messaggio in attesa, avviando ricerca automatica:', pendingSearch);
    
    // Rimuovi il messaggio dal sessionStorage
    sessionStorage.removeItem('pending_search');
    
    // NON inserire il messaggio nella barra di ricerca, mantienila pulita
    // Avvia direttamente la ricerca senza popolare l'input
    setTimeout(() => {
      console.log('🚀 Avviando ricerca automatica...');
      const event = new Event('submit');
      event.searchTerm = pendingSearch; // Passa il termine direttamente
      document.getElementById('search-form').dispatchEvent(event);
    }, 500);
  }
  try {
    const retSel = sessionStorage.getItem('return_to_selection');
    const saveAfterLogin = sessionStorage.getItem('save_after_login');
    // Esegui lo switch automatico alla Selezione solo nel flusso post-login
    if (retSel === '1' && saveAfterLogin === '1') {
      try { window.__USER_NAV_ACTIVE__ = true; } catch (e) {}
      showResultsPage('selection');
      try { sessionStorage.removeItem('return_to_selection'); } catch (e) {}
    }
  } catch (e) {}
  
  // Rimosso focus automatico per evitare scroll indesiderato
  // if (searchInput) {
  //   searchInput.focus();
  // }
});

// Gestione del ridimensionamento automatico dell'input (se necessario in futuro)
// e miglioramenti UX per l'interfaccia chatbot
const searchInputReactive = document.getElementById('search-input');
if (searchInputReactive) {
  searchInputReactive.addEventListener('input', (event) => {
    const clearButton = document.getElementById('clear-button');
    const submitButton = document.querySelector('button[type="submit"]');
    const empty = event.target.value.trim() === '';
    if (clearButton) clearButton.style.opacity = empty ? '0.5' : '1';
    if (submitButton) submitButton.style.opacity = empty ? '0.5' : '1';
  });
}

// Rimossa la funzione scrollToBottom per evitare scroll automatici indesiderati

// Rimosso lo scroll automatico dalla funzione showAILoadingAnimation
// per evitare scroll indesiderati durante il caricamento

// Gestione del chatbot

// Funzione per aggiungere l'indicatore di digitazione
function addTypingIndicator() {
  const chatbotMessages = document.getElementById('chatbot-messages');
  if (!chatbotMessages) return;
  
  // Rimuovi eventuali indicatori di digitazione esistenti
  removeTypingIndicator();
  
  const typingElement = document.createElement('div');
  typingElement.className = 'flex justify-start mb-2';
  typingElement.id = 'typing-indicator';
  typingElement.innerHTML = `
    <div class="bg-gray-100 text-gray-800 rounded-lg px-3 py-2 max-w-[80%] text-sm">
      <div class="typing-indicator">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>
  `;
  // Aggiungi l'indicatore di digitazione al container
  chatbotMessages.appendChild(typingElement);
  
  // Scroll automatico verso l'indicatore di digitazione
  typingElement.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

// Funzione per rimuovere l'indicatore di digitazione
function removeTypingIndicator() {
  const typingIndicator = document.getElementById('typing-indicator');
  if (typingIndicator) {
    typingIndicator.remove();
  }
}

// Funzione per aggiungere messaggi al chatbot


function addChatbotMessage(message, isUser = false) {
  console.log('addChatbotMessage chiamata con:', message, isUser);
  const chatbotMessages = document.getElementById('chatbot-messages');
  console.log('Elemento chatbot-messages trovato:', chatbotMessages);
  
  if (!chatbotMessages) {
    console.error('Elemento chatbot-messages non trovato!');
    return;
  }
  
  // Intercetta la parola "ricarico" nelle risposte del bot
  if (!isUser && message.toLowerCase().trim() === 'ricarico') {
    console.log('🔄 Rilevata parola "ricarico" - uscita dalla modalità chatbot e avvio nuova ricerca');
    console.log('🗺️ Località corrente memorizzata:', currentLocation);
    
    // Ottieni l'ultimo messaggio dell'utente dalla cronologia PRIMA di resettarla
    const lastUserMessage = messageHistory
      .slice()
      .reverse()
      .find(msg => msg.role === 'user');
    
    // Disabilita la modalità chatbot
    chatbotModeActive = false;
    console.log('🤖 Modalità chatbot disabilitata');
    
    // Pulisci i risultati esistenti
    const resultsContainer = document.getElementById('results-container');
    if (resultsContainer) {
      resultsContainer.innerHTML = '';
      console.log('🧹 Risultati precedenti puliti');
    }
    
    // Reset della cronologia messaggi
    messageHistory = [];
    console.log('📝 Cronologia messaggi resettata');
    
    if (lastUserMessage && lastUserMessage.parts && lastUserMessage.parts[0] && lastUserMessage.parts[0].text) {
      const userQuery = lastUserMessage.parts[0].text;
      console.log('🔄 Ultimo messaggio utente trovato:', userQuery);
      
      // Avvia una nuova ricerca con il messaggio dell'utente
      setTimeout(() => {
        console.log('🚀 Avvio nuova ricerca con prompt originale:', userQuery);
        const event = new Event('submit');
        event.searchTerm = userQuery;
        document.getElementById('search-form').dispatchEvent(event);
      }, 100);
      
      return; // Non aggiungere il messaggio "ricarico" al chatbot
    } else {
      console.error('🔄 Impossibile trovare l\'ultimo messaggio dell\'utente per riavviare la ricerca');
    }
  }
  
  // Rimuovi l'indicatore di digitazione se presente
  removeTypingIndicator();
  
  const norm = toPlainText(String(message || '')).replace(/\s+/g, ' ').trim();
  const last = window.__LAST_CHAT_MSG__;
  if (last && last.text === norm) { return; }
  
  // Rimuovi il messaggio di benvenuto se presente
  const welcomeMessage = chatbotMessages.querySelector('.text-center');
  if (welcomeMessage) {
    welcomeMessage.remove();
  }
  
  const messageElement = document.createElement('div');
  messageElement.className = isUser ? 'flex justify-end mb-2' : 'flex justify-start mb-2';
  messageElement.innerHTML = `
    <div class="${isUser ? 'bg-[#0c7ff2] text-white' : 'bg-gray-100 text-gray-800'} rounded-lg px-3 py-2 max-w-[80%] text-sm">
      ${message}
    </div>
  `;
  // Aggiungi il messaggio al container
  chatbotMessages.appendChild(messageElement);
  
  try { window.__LAST_CHAT_MSG__ = { text: toPlainText(String(message || '')).replace(/\s+/g, ' ').trim(), isUser: !!isUser }; } catch (e) {}
  
  // Aggiungi il messaggio alla cronologia se non è dell'utente (già aggiunto in precedenza)
  if (!isUser) {
    messageHistory.push({ role: 'model', parts: [{ text: message }] });
  }
  
  // Scroll automatico verso l'ultimo messaggio
  messageElement.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

// Funzione per aprire il modal con i dettagli dell'attività
function openActivityModal(placeId, activityName) {
  console.log('Apertura modal per:', placeId, activityName);
  
  // Crea il modal se non esiste
  let modal = document.getElementById('activity-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'activity-modal';
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 hidden';
    modal.innerHTML = `
      <div class="bg-white rounded-lg max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div class="flex justify-between items-center p-6 border-b">
          <h2 id="modal-title" class="text-2xl font-bold text-gray-800">Dettagli Attività</h2>
          <button onclick="closeActivityModal()" class="text-gray-500 hover:text-gray-700 text-2xl">&times;</button>
        </div>
        <div id="modal-content" class="p-6">
          <div class="flex items-center justify-center py-8">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            <span class="ml-2 text-gray-600">Caricamento dettagli...</span>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }
  
  // Aggiorna il titolo del modal
  document.getElementById('modal-title').textContent = activityName || 'Dettagli Attività';
  
  // Mostra il modal
  modal.classList.remove('hidden');
  
  // Carica i dettagli dell'attività
  loadActivityDetails(placeId, activityName);
}

// Funzione per chiudere il modal
function closeActivityModal() {
  const modal = document.getElementById('activity-modal');
  if (modal) {
    modal.classList.add('hidden');
  }
}

// Funzione per caricare i dettagli dell'attività
async function loadActivityDetails(placeId, activityName) {
  const modalContent = document.getElementById('modal-content');

  // Gestione immediata degli ID pseudo: non chiamare l'API backend
  const isPseudoEarly = typeof placeId === 'string' && placeId.startsWith('gemini-');
  if (isPseudoEarly) {
    const apiKey = 'AIzaSyC92HQzyCZ2QTTvAPuRSq0hCnpnWAXsfAk';
    const safeName = (activityName || '').trim();
    const iframeSrc = `https://www.google.com/maps/embed/v1/search?key=${apiKey}&q=${encodeURIComponent(safeName || 'Italia')}`;
    const mapsHref = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(safeName || 'Italia')}`;
    modalContent.innerHTML = `
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h3 class="text-xl font-semibold text-gray-800 mb-4">Informazioni generali</h3>
          <div class="space-y-2 text-sm">
            <p class="text-gray-600">Dettagli non disponibili: manca un place_id reale per questa attività.</p>
          </div>
        </div>
        <div>
          <h3 class="text-xl font-semibold text-gray-800 mb-4">Mappa</h3>
          <div class="w-full h-64 bg-gray-200 rounded-lg overflow-hidden">
            <iframe width="100%" height="100%" frameborder="0" style="border:0" src="${iframeSrc}" allowfullscreen></iframe>
          </div>
        </div>
      </div>
      <div class="mt-6 flex justify-center">
        <a href="${mapsHref}" target="_blank" class="bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded-lg transition-colors">Apri in Google Maps</a>
      </div>
    `;
    return;
  }

  try {
    const response = await fetch(`/api/place_details/${placeId}`);
    if (!response.ok) {
      throw new Error(`Errore HTTP: ${response.status}`);
    }
    
    const details = await response.json();
    
    if (details.error) {
      modalContent.innerHTML = `
        <div class="text-center py-8">
          <p class="text-red-600">Errore nel caricamento dei dettagli: ${details.error}</p>
        </div>
      `;
      return;
    }
    
    // Costruisci l'HTML con i dettagli
    let photoHtml = '';
    if (details.photo_url) {
      photoHtml = `
        <div class="mb-6">
          <img src="${details.photo_url}" alt="${details.name || 'Attività'}" class="w-full h-64 object-cover rounded-lg">
        </div>
      `;
    }
    
    let openingHoursHtml = '';
    if (details.opening_hours && details.opening_hours.weekday_text) {
      openingHoursHtml = `
        <div class="mb-4">
          <h4 class="font-semibold text-gray-800 mb-2">Orari di apertura:</h4>
          <ul class="text-sm text-gray-600 space-y-1">
            ${details.opening_hours.weekday_text.map(day => `<li>${day}</li>`).join('')}
          </ul>
        </div>
      `;
    }
    
    let reviewsHtml = '';
    if (details.reviews && details.reviews.length > 0) {
      reviewsHtml = `
        <div class="mb-4">
          <h4 class="font-semibold text-gray-800 mb-2">Recensioni recenti:</h4>
          <div class="space-y-3">
            ${details.reviews.slice(0, 3).map(review => `
              <div class="bg-gray-50 p-3 rounded-lg">
                <div class="flex items-center mb-2">
                  <span class="font-medium text-sm">${review.author_name || 'Anonimo'}</span>
                  <span class="ml-2 text-yellow-500">${'★'.repeat(review.rating || 0)}</span>
                </div>
                <p class="text-sm text-gray-600">${review.text || 'Nessun commento'}</p>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }
    
    // Determina se il placeId è pseudo (generato) e prepara src dell'iframe e link Google Maps
    const isPseudo = typeof placeId === 'string' && placeId.startsWith('gemini-');
    const apiKey = 'AIzaSyC92HQzyCZ2QTTvAPuRSq0hCnpnWAXsfAk';
    const safeName = (activityName || details.name || '').trim();
    const iframeSrc = isPseudo
      ? `https://www.google.com/maps/embed/v1/search?key=${apiKey}&q=${encodeURIComponent(safeName || 'Italia')}`
      : `https://www.google.com/maps/embed/v1/place?key=${apiKey}&q=place_id:${placeId}`;
    const mapsHref = isPseudo
      ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(safeName || 'Italia')}`
      : `https://www.google.com/maps/place/?q=place_id:${placeId}`;

    modalContent.innerHTML = `
      ${photoHtml}
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h3 class="text-xl font-semibold text-gray-800 mb-4">Informazioni generali</h3>
          <div class="space-y-2 text-sm">
            <p><strong>Indirizzo:</strong> ${details.formatted_address || 'Non disponibile'}</p>
            <p><strong>Telefono:</strong> ${details.international_phone_number || details.formatted_phone_number || 'Non disponibile'}</p>
            <p><strong>Valutazione:</strong> ${details.rating ? `⭐ ${details.rating}` : 'Non disponibile'} ${details.user_ratings_total ? `(${details.user_ratings_total} recensioni)` : ''}</p>
            <p><strong>Fascia di prezzo:</strong> ${details.price_level ? '€'.repeat(details.price_level) : 'Non specificata'}</p>
            ${details.website ? `<p><strong>Sito web:</strong> <a href="${details.website}" target="_blank" class="text-blue-500 hover:underline">${details.website}</a></p>` : ''}
            <p><strong>Tipo:</strong> ${details.types ? details.types.slice(0, 3).join(', ') : 'Non specificato'}</p>
          </div>
          ${openingHoursHtml}
        </div>
        <div>
          <h3 class="text-xl font-semibold text-gray-800 mb-4">Mappa</h3>
          <div class="w-full h-64 bg-gray-200 rounded-lg overflow-hidden">
            <iframe
              width="100%"
              height="100%"
              frameborder="0"
              style="border:0"
              src="${iframeSrc}"
              allowfullscreen>
            </iframe>
          </div>
        </div>
      </div>
      ${reviewsHtml}
      <div class="mt-6 flex justify-center">
        <a href="${mapsHref}" target="_blank" class="bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded-lg transition-colors">
          Apri in Google Maps
        </a>
      </div>
    `;
    
  } catch (error) {
    console.error('Errore nel caricamento dei dettagli:', error);
    modalContent.innerHTML = `
      <div class="text-center py-8">
        <p class="text-red-600">Errore nel caricamento dei dettagli: ${error.message}</p>
        <button onclick="loadActivityDetails('${placeId}')" class="mt-4 bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded transition-colors">
          Riprova
        </button>
      </div>
    `;
  }
}

// Chiudi il modal quando si clicca fuori da esso
document.addEventListener('click', function(event) {
  const modal = document.getElementById('activity-modal');
  if (modal && event.target === modal) {
    closeActivityModal();
  }
});

// Chiudi il modal con il tasto Escape



let manualSelection = [];
// Array che mantiene i locali presenti in "Altri suggerimenti"
let suggests = [];


// I locali caricati dal JSON sono mostrati SOLO nella seconda pagina (La nostra selezione).

// Caricamento automatico della selezione dal JSON all'avvio se vuota









/* document.addEventListener('click', (e) => {
    const btn = e.target.closest('.add-to-trip-btn');
    if (btn) {
        const card = btn.closest('.activity-card');
        if (!card) return;
        const placeId = btn.dataset.placeId || card.dataset?.placeId || card.getAttribute('data-place-id') || extractPlaceId(card);
        if (!placeId) return;
        addActivity(placeId, card);
        return;
    }
    const link = e.target.closest('a.selection-card-link');
    if (link) {
        e.preventDefault();
        e.stopPropagation();
        const card = link.closest('.activity-card');
        const placeId = (card && (card.dataset?.placeId || card.getAttribute('data-place-id'))) || extractPlaceId(card) || link.getAttribute('data-place-id');
        const nameEl = card ? (card.querySelector('h3, h4, .city-title')) : null;
        const activityName = nameEl ? nameEl.textContent.trim() : (link.getAttribute('data-name') || '');
        if (placeId) {
            openActivityModal(placeId, activityName);
        }
        return;
    }
}); */


document.addEventListener('click', (e) => {
    const btn = e.target.closest('.add-to-trip-btn');
    if (!btn) return;

    const card = btn.closest('.activity-card');
    if (!card) return;

    const placeId = btn.dataset.placeId || card.dataset?.placeId || card.getAttribute('data-place-id') || extractPlaceId(card);
    if (!placeId) return;

    addActivity(placeId, card);
});







// Rimozione card (delegato) per qualsiasi bottone "meno" presente in griglia




function extractPlaceId(card) {
    // 1) Data attribute diretto
    const da = card.dataset?.placeId || card.getAttribute('data-place-id');
    if (da) return da;
    // 2) Onclick con openActivityModal('PLACE_ID')
    const onclick = card.getAttribute('onclick');
    const match = onclick?.match(/openActivityModal\('(.+?)'/);
    if (match && match[1]) return match[1];
    // 3) Link interno verso Google Maps con place_id
    const link = card.querySelector('a[href*="place_id:"]');
    if (link && link.href) {
        const m = link.href.match(/place_id:([^&]+)/);
        if (m && m[1]) return m[1];
    }
    return null;
}

/* function addActivity(placeId, card) {
    // Invia evento di aggiunta: la logica di sincronizzazione vive nei listener
    const activity = extractActivityInfo(card);
    const inLfw = !!(card && card.closest && card.closest('#page-lfw'));
    const ev = new CustomEvent('selection:add', { detail: { activity, source: inLfw ? 'lfw' : 'other' } });
    document.dispatchEvent(ev);
}
 */

function addActivity(placeId, card) {
    if (manualSelection.some(a => a.place_id === placeId)) return;

    const activity = extractActivityInfo(card);
    manualSelection.push(activity);
    setCardSelected(card, true);
    updateSelectionUI();
	if (window.mapManager && typeof window.mapManager.updateItinerary === 'function') {
		window.mapManager.updateItinerary(manualSelection);
	}
    try { dedupeOurSelection(); } catch (e) {}
    try { localStorage.setItem('manual_selection', JSON.stringify(manualSelection)); } catch (e) {}
}






document.addEventListener("click", function (event) {
    const btn = event.target.closest(".minus-btn");
    if (!btn) return;

    event.stopPropagation(); // BLOCCA LA CARD DAL CATTURARE IL CLICK

    const placeId = btn.dataset.placeId;
    if (!placeId) return;

    removeSelectedActivity(placeId, btn);
});







function removeSelectedActivity(placeId, btnEl) {
    // rimuove dal dataset manualSelection
    
        manualSelection = manualSelection.filter(a => a.place_id !== placeId);
        
  

    // rimuovi la card dal DOM
    const card = btnEl.closest(".activity-card");
    if (card) {
        card.remove();
        
    }
        restorePlusButton(placeId);
    // aggiorna la UI
    if (typeof updateSelectionUI === "function") {
        updateSelectionUI();
		if (window.mapManager && typeof window.mapManager.updateItinerary === 'function') {
			window.mapManager.updateItinerary(manualSelection);
		}
    }
    try { dedupeOurSelection(); } catch (e) {}
    try { localStorage.setItem('manual_selection', JSON.stringify(manualSelection)); } catch (e) {}
}




/* function removeSelectedActivity(placeId, btnEl) {
    // Prepara i dettagli attività PRIMA della rimozione dal DOM
    let activity = null;
    try {
      const card = btnEl ? btnEl.closest('.activity-card') : null;
      if (card) activity = extractActivityInfo(card);
    } catch (err) {}
    // Invia evento di rimozione con i dettagli per reinserimento in suggests
    const ev = new CustomEvent('selection:remove', { detail: { place_id: placeId, activity } });
    document.dispatchEvent(ev);
} */

function restorePlusButton(placeId) {
    const suggestionCard = document.querySelector(
        `.activity-card[data-place-id="${placeId}"]`
    );
    if (!suggestionCard) return;

    // Usa la funzione centralizzata per ripristinare lo stato del bottone (bianco)
    setCardSelected(suggestionCard, false);
}

// Listener eventi per sincronizzare selezione e suggerimenti
document.addEventListener('selection:add', (e) => {
  const act = (e && e.detail && e.detail.activity) || null;
  const source = (e && e.detail && e.detail.source) || 'other';
  if (!act || !act.place_id) return;
  if (!Array.isArray(manualSelection)) manualSelection = [];
  if (manualSelection.some(a => a.place_id === act.place_id)) return;
  manualSelection.push(act);
  // Se proveniente da LFW o dalla griglia suggerimenti, pulisci la card e aggiorna suggests
  try {
    if (source === 'lfw' || source === 'suggests') {
      suggests = Array.isArray(suggests) ? suggests.filter(s => s.place_id !== act.place_id) : [];
      const sugGrid = document.getElementById('suggestions-grid');
      if (sugGrid) {
        const el = sugGrid.querySelector(`.activity-card[data-place-id="${act.place_id}"]`);
        if (el) el.remove();
      }
      const lfw = document.getElementById('page-lfw');
      if (lfw) {
        const el = lfw.querySelector(`.activity-card[data-place-id="${act.place_id}"]`);
        if (el) el.remove();
      }
    }
  } catch (err) {}
  // Aggiorna UI e persistenza
  if (typeof updateSelectionUI === 'function') updateSelectionUI();
  if (window.mapManager && typeof window.mapManager.orderActivitiesByDistance === 'function') {
    window.mapManager.orderActivitiesByDistance(manualSelection[0], manualSelection)
      .then(sortedActivities => {
        window.mapManager.updateItinerary(sortedActivities);
      });
  }

  
  try { dedupeOurSelection(); } catch (e) {}
  try { localStorage.setItem('manual_selection', JSON.stringify(manualSelection)); } catch (e) {}
  updateSaveItineraryButtonVisibility();
  // Autosalva cache città appena compaiono elementi utili
  try { maybeAutoSaveCityCache('user'); } catch (e) {}
});

document.addEventListener('selection:remove', (e) => {
  const placeId = (e && e.detail && e.detail.place_id) || null;
  const actDetail = (e && e.detail && e.detail.activity) || null;
  if (!placeId) return;
  manualSelection = Array.isArray(manualSelection) ? manualSelection.filter(a => a.place_id !== placeId) : [];
  // Rimuovi card dalla griglia Selezione, se presente
  try {
    const selCard = document.querySelector(`#page-selection .activity-card[data-place-id="${placeId}"]`);
    if (selCard) selCard.remove();
  } catch (err) {}
  // Usa i dettagli passati dall'evento per reinserire in suggests
  const act = actDetail || null;
  if (act && act.place_id) {
    if (!Array.isArray(suggests)) suggests = [];
    if (!suggests.some(s => s.place_id === act.place_id)) {
      // Normalizza e imposta categoria/type se assenti
      try {
        const cat = getActCategoryForLfw(act);
        if (cat) {
          if (!act.category) act.category = cat;
          if (!act.type) act.type = cat;
        }
      } catch (err) {}
      suggests.push(act);
      // Inserisci direttamente in LFW nella sezione corretta basandoti su act.type/category
      try { insertActIntoLfwOrQueue(act); } catch (e) {}
    }
  }
  restorePlusButton(placeId);
  if (typeof updateSelectionUI === 'function') updateSelectionUI();


  if (
  window.mapManager &&
  typeof window.mapManager.orderActivitiesByDistance === 'function'
) {
  window.mapManager
    .orderActivitiesByDistance(manualSelection[0], manualSelection)
    .then(sortedActivities => {
      window.mapManager.updateItinerary(sortedActivities);
    });
}

  try { dedupeOurSelection(); } catch (e) {}
  try { localStorage.setItem('manual_selection', JSON.stringify(manualSelection)); } catch (e) {}
  updateSaveItineraryButtonVisibility();
});

// Eventi per gestione diretta dei suggerimenti
document.addEventListener('suggests:add', (e) => {
  const act = (e && e.detail && e.detail.activity) || null;
  const render = !(e && e.detail && e.detail.render === false);
  if (!act || !act.place_id) return;
  if (!Array.isArray(suggests)) suggests = [];
  if (!suggests.some(s => s.place_id === act.place_id)) {
    // Normalizza categoria/type quando si aggiunge a suggests
    try {
      const cat = getActCategoryForLfw(act);
      if (cat) {
        if (!act.category) act.category = cat;
        if (!act.type) act.type = cat;
      }
    } catch (err) {}
    suggests.push(act);
    if (render) renderSuggestionCard(act);
  }
  // Autosalva cache città quando i suggerimenti vengono popolati
  try { maybeAutoSaveCityCache('user'); } catch (e) {}
});

document.addEventListener('suggests:remove', (e) => {
  const placeId = (e && e.detail && e.detail.place_id) || null;
  if (!placeId) return;
  suggests = Array.isArray(suggests) ? suggests.filter(s => s.place_id !== placeId) : [];
  const grid = document.getElementById('suggestions-grid');
  if (grid) {
    const el = grid.querySelector(`.activity-card[data-place-id="${placeId}"]`);
    if (el) el.remove();
  }
});

// Griglia e rendering dei suggerimenti
function ensureSuggestionsGrid() {
  // Rimuove la sezione "Suggerimenti" dalla terza pagina (LFW) e non la ricrea più
  const pageLfw = document.getElementById('page-lfw');
  if (!pageLfw) return;
  const sugSection = document.getElementById('suggestions-section');
  if (sugSection) {
    try { sugSection.remove(); } catch (e) {}
  }
  // Non creare più il grid dei suggerimenti
}

function collectLfwSuggestions() {
  const pageLfw = document.getElementById('page-lfw');
  if (!pageLfw) return;
  const cards = pageLfw.querySelectorAll('.activity-card');
  cards.forEach(card => {
    try {
      const act = extractActivityInfo(card);
      if (!act || !act.place_id) return;
      const alreadySelected = Array.isArray(manualSelection) && manualSelection.some(a => a.place_id === act.place_id);
      if (alreadySelected) return;
      const ev = new CustomEvent('suggests:add', { detail: { activity: act, render: false } });
      document.dispatchEvent(ev);
    } catch (err) {}
  });
}

function renderSuggestionCard(act) {
  ensureSuggestionsGrid();
  const grid = document.getElementById('suggestions-grid');
  if (!grid || !act) return;
  const card = document.createElement('div');
  card.className = 'activity-card';
  card.setAttribute('data-place-id', act.place_id || '');
  var __reviews = (typeof act.reviews !== 'undefined' ? act.reviews : act.reviews_count);
  if (__reviews !== undefined && __reviews !== null) {
  card.setAttribute('data-reviews', String(__reviews));
}
  card.setAttribute('data-address', act.address || '');
  if (act.location && typeof act.location.lat === 'number' && typeof act.location.lng === 'number') {
    card.setAttribute('data-lat', String(act.location.lat));
    card.setAttribute('data-lng', String(act.location.lng));
  }
  const imgHtml = act.image ? `<div class=\"w-full bg-center bg-no-repeat aspect-[4/3] bg-cover\" style='background-image: url(\"${act.image}\");'></div>` : '<div class=\"w-full bg-slate-200 aspect-[4/3] flex items-center justify-center\"><span class=\"material-icons text-slate-400 text-4xl\">place</span></div>';
  const ratingText = act.rating ? `<p class=\"rating text-slate-600 text-sm mt-1\">${act.rating}</p>` : '';
  card.innerHTML = `
    ${imgHtml}
    <div class=\"p-5 flex flex-col flex-grow\">
      <h4 class=\"text-slate-800 text-lg font-semibold leading-snug\">${act.name || 'Nome non disponibile'}</h4>
      <p class=\"text-slate-600 text-sm font-normal leading-normal mt-1 flex-grow\">${act.address || 'Indirizzo non disponibile'}</p>
      ${ratingText}
      <div class=\"mt-3 flex items-center justify-end\">
        <button class=\"add-to-trip-btn bg-[#b7f056] text-[#0f3e34] font-bold rounded-full w-8 h-8 flex items-center justify-center\" data-place-id=\"${act.place_id}\">+</button>
      </div>
    </div>
  `;
  // click su + nella card suggerimenti -> dispatch selection:add
  const btn = card.querySelector('.add-to-trip-btn');
  if (btn) {
    btn.addEventListener('click', (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const ce = new CustomEvent('selection:add', { detail: { activity: act, source: 'suggests' } });
      document.dispatchEvent(ce);
    });
  }
  grid.appendChild(card);
}



// ===== Helpers LFW: normalizzazione categoria, ricerca griglia, creazione e inserimento card =====
function normalizeToAllowedLfwCategory(cat) {
  const raw = String(cat || '').toLowerCase().trim();
  if (!raw || raw === 'la_nostra_selezione') return '';
  if (/(ristoranti|ristorante|cucina|piatti|dishes|food|trattorie|osterie|pizzerie)/.test(raw)) return 'cucina_tipica';
  if(/(dolci|pasticcerie|dessert|torte|gelaterie)/.test(raw)) return 'dolci tipici';
  if (/(vini|bevande|wine|drink|enoteca|cantine)/.test(raw)) return 'vini';
  if (/(hotel|albergo|ospiti|stay|strutture\s*ricettive)/.test(raw)) return 'hotel';
  // già ammessi
  if (raw === 'cucina_tipica'||raw === 'dolci tipici' || raw === 'vini' || raw === 'hotel') return raw;
  return '';
}

function getActCategoryForLfw(act) {
  let cat = normalizeToAllowedLfwCategory(act?.type || act?.category || '');
  if (cat) return cat;
  // Heuristica su nome/indirizzo quando la categoria è assente
  const text = `${act?.name || ''} ${act?.address || ''}`.toLowerCase();
  if (/(hotel|albergo|resort|b\s*&\s*b|bnb|bed\s*and\s*breakfast)/.test(text)) return 'hotel';
  if (/(pasticceria|dolce|dessert|gelateria|torta)/.test(text)) return 'dolci tipici';
  if (/(vino|cantina|enoteca|wine)/.test(text)) return 'vini';
  if (/(ristorante|trattoria|osteria|pizzeria|cucina|food)/.test(text)) return 'cucina_tipica';

  return '';
}

function findLfwCategoryGrid(category) {
  const pageLfw = document.getElementById('page-lfw');
  if (!pageLfw) return null;
  const cat = normalizeToAllowedLfwCategory(category);
  if (!cat) return null;
  // 1) Ricerca primaria: match su [data-category] normalizzato
  const candidates = Array.from(pageLfw.querySelectorAll('[data-category]'));
  const match = candidates.find(el => normalizeToAllowedLfwCategory(el.getAttribute('data-category')) === cat);
  if (match) {
    const grid = match.querySelector('.activities-grid') || match.querySelector('.category-results') || match.querySelector('.grid');
    return grid || match;
  }
  // 2) Fallback: classi/sezioni note
  let section = null;
  if (cat === 'cucina_tipica') {
    section = pageLfw.querySelector('.dishes-section') || pageLfw.querySelector('.piatti-section') || Array.from(pageLfw.querySelectorAll('h2, h3')).find(h => /primi\s*piatti(\s*tipici)?|piatti\s*tipici/i.test(h.textContent))?.closest('div');
  }else if (cat === 'dolci tipici') {
    section = pageLfw.querySelector('.desserts-section') || Array.from(pageLfw.querySelectorAll('h2, h3')).find(h => /dolci|dessert|pasticcerie/i.test(h.textContent))?.closest('div');
  } else if (cat === 'vini') {
    section = pageLfw.querySelector('.wines-section') || Array.from(pageLfw.querySelectorAll('h2, h3')).find(h => /vini(\s*&\s*bevande)?/i.test(h.textContent))?.closest('div');
  } else if (cat === 'hotel') {
    section = pageLfw.querySelector('.hotels-section') || Array.from(pageLfw.querySelectorAll('h2, h3')).find(h => /hotel|alberghi|dove\s*dormire/i.test(h.textContent))?.closest('div');
  } 
  if (!section) return null;
  const grid = section.querySelector('.grid') || section;
  return grid;
}

function ensureLfwDynamicSuggestionsSection() {
  const pageLfw = document.getElementById('page-lfw');
  if (!pageLfw) return null;
  let section = pageLfw.querySelector('#lfw-dynamic-suggestions');
  if (!section) {
    section = document.createElement('div');
    section.id = 'lfw-dynamic-suggestions';
    section.className = 'p-2 ml-6 md:ml-8 xl:ml-10';
    const header = document.createElement('div');
    header.className = 'mb-4';
    header.innerHTML = '<h3 class="text-2xl font-semibold text-[#0f3e34]">Altri Suggerimenti</h3>';
    const grid = document.createElement('div');
    grid.className = 'grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch';
    section.appendChild(header);
    section.appendChild(grid);
    pageLfw.appendChild(section);
  }
  return section.querySelector('.grid');
}

function createLfwCardElement(act, category) {
  const card = document.createElement('div');
  card.className = 'activity-card';
  card.setAttribute('data-place-id', act.place_id || '');
  card.setAttribute('data-address', act.address || '');
  if (category) card.setAttribute('data-category', category);
  if (act.location && typeof act.location.lat === 'number' && typeof act.location.lng === 'number') {
    card.setAttribute('data-lat', String(act.location.lat));
    card.setAttribute('data-lng', String(act.location.lng));
  }
  // Stili inline e struttura coerenti con FilteringRankingService._format_to_html
  card.style.cssText = [
    'border: 1px solid #e2e8f0',
    'border-radius: 12px',
    'padding: 10px',
    'background: white',
    'box-shadow: 0 2px 8px rgba(0,0,0,0.1)',
    'transition: transform 0.2s, box-shadow 0.2s',
    'min-height: 380px',
    'display: flex',
    'flex-direction: column',
    'justify-content: space-between',
    'overflow: hidden',
    'cursor: pointer'
  ].join('; ');
  card.setAttribute('onmouseover', "this.style.transform='translateY(-4px)'; this.style.boxShadow='0 4px 16px rgba(0,0,0,0.15)'");
  card.setAttribute('onmouseout', "this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.1)'");

  // Immagine + overlay pulsante "+" compatibile
  const photoUrl = act.image || '';
  const imageCore = photoUrl
    ? `<div class="activity-image" style="width: 250px; height: 200px; background-image: url(${photoUrl}); background-size: cover; background-position: center; border-radius: 8px 8px 0 0; margin: -16px -16px 12px -16px;"></div>`
    : '<div class="activity-image" style="width: 100%; height: 150px; background: #eaeaea; border-radius: 8px 8px 0 0; margin: -16px -16px 12px -16px;"></div>';
  const imageHtml = `<div style="position: relative;">${imageCore}<button type="button" class="add-to-trip-btn" title="Aggiungi" style="position: absolute; top: 10px; right: 10px; background: #ffffff; border-radius: 9999px; padding: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.08); border: none; cursor: pointer;"><span class="material-icons" style="color: #0f3e34; font-size: 16px; font-weight: 700;">add</span></button></div>`;

  const ratingText = act.rating ? `<p class="rating" style="margin-bottom: 0px; font-size: 0.875rem; color: #334155;"><b>⭐ ${act.rating}</b></p>` : '';
  const mapsUrl = buildMapsUrl(act);
  const escapedName = String(act.name || '').replace(/'/g, "&#39;");
  const linksHtml = `<div class="links" style="margin-top: 0px;"><a href="${mapsUrl}" target="_blank" class="selection-card-link" onclick="openActivityModal('${act.place_id}','${escapedName}'); return false;" style="display: inline-flex; align-items: center; gap: 6px; text-decoration: none;font-size: 0.875rem; font-weight: 600; color: #0f3e34;">Visualizza la scheda<span class="material-icons" style="font-size: 16px; line-height: 1; color: #0f3e34;">arrow_forward</span></a></div>`;

  card.innerHTML = `
    ${imageHtml}
    <div style="padding-top: 4px;">
      <h3 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 2px; line-height: 1.25; color: #0f172a;">${act.name || 'Nome non disponibile'}</h3>
      ${ratingText}
    </div>
    <div style="padding-top: 0px;">${linksHtml}</div>
  `;

  const btn = card.querySelector('.add-to-trip-btn');
  if (btn) {
    btn.setAttribute('data-place-id', act.place_id || '');
    btn.addEventListener('click', (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const ce = new CustomEvent('selection:add', { detail: { activity: act, source: 'lfw' } });
      document.dispatchEvent(ce);
    });
  }
  return card;
}

// Coda per reinserimenti quando la pagina LFW non è pronta
var pendingLfwActs = Array.isArray(window.pendingLfwActs) ? window.pendingLfwActs : [];
try { window.pendingLfwActs = pendingLfwActs; } catch (e) {}

function insertActIntoLfwOrQueue(act) {
  if (!act || !act.place_id) return;
  const cat = getActCategoryForLfw(act);
  let grid = findLfwCategoryGrid(cat);
  if (!grid) {
    // Fallback: se la sezione di categoria non esiste, usa "Altri Suggerimenti"
    grid = ensureLfwDynamicSuggestionsSection();
  }
  if (grid) {
    // Evita duplicati
    const exists = grid.querySelector(`.activity-card[data-place-id="${act.place_id}"]`);
    if (exists) return;
    const card = createLfwCardElement(act, cat);
    grid.appendChild(card);
    try { if (typeof hideProgramLoading === 'function') hideProgramLoading(); } catch (e) {}
  } else {
    pendingLfwActs.push(act);
  }
}

function drainPendingLfwActs() {
  if (!Array.isArray(pendingLfwActs) || pendingLfwActs.length === 0) {
    // Se non ci sono atti pendenti, assicurati comunque che l'overlay di caricamento sia nascosto
    try { if (typeof hideProgramLoading === 'function') hideProgramLoading(); } catch (e) {}
    return;
  }
  const rest = [];
  for (const act of pendingLfwActs) {
    const cat = getActCategoryForLfw(act);
    let grid = findLfwCategoryGrid(cat);
    if (!grid) grid = ensureLfwDynamicSuggestionsSection();
    if (grid) {
      const exists = grid.querySelector(`.activity-card[data-place-id="${act.place_id}"]`);
      if (!exists) {
        const card = createLfwCardElement(act, cat);
        grid.appendChild(card);
      }
    } else {
      rest.push(act);
    }
  }
  pendingLfwActs = rest;
  try { window.pendingLfwActs = pendingLfwActs; } catch (e) {}
  // Quando i contenuti pendenti sono stati processati, nascondi l'overlay
  try { if (typeof hideProgramLoading === 'function') hideProgramLoading(); } catch (e) {}
}

// Helper: genera URL Maps analogo al servizio Python
function buildMapsUrl(act) {
  try {
    const placeId = act && act.place_id;
    if (placeId && !String(placeId).startsWith('gemini-')) {
      return `https://www.google.com/maps/place/?q=place_id:${String(placeId)}`;
    }
    const name = act && (act.name || '');
    const address = act && (act.address || '');
    const query = `${name} ${address}`.trim() || name || address;
    if (query) {
      return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
    }
    const lat = act && act.location && act.location.lat;
    const lng = act && act.location && act.location.lng;
    if (typeof lat === 'number' && typeof lng === 'number') {
      return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(String(lat))}%2C${encodeURIComponent(String(lng))}`;
    }
    return 'https://www.google.com/maps';
  } catch (e) {
    return 'https://www.google.com/maps';
  }
}

function setCardSelected(card, isSelected) {
  const btn = card.querySelector('.add-to-trip-btn');
  if (!btn) return;

  if (isSelected) {
    btn.innerHTML = '✓';
    btn.classList.add('added');
    btn.classList.add('bg-[#b8f36d]');
    btn.classList.remove('bg-[#ffffff]');
    // Imposta sia background che backgroundColor per forzare il colore
    btn.style.background = '#b8f36d';
    btn.style.backgroundColor = '#b8f36d';
    btn.disabled = true;
  } else {
    btn.innerHTML = '+';
    btn.classList.add('bg-[#ffffff]');
    btn.classList.remove('bg-[#b8f36d]');
    btn.classList.remove('added');
    // Imposta sia background che backgroundColor per forzare il colore
    btn.style.background = '#ffffff';
    btn.style.backgroundColor = '#ffffff';
    btn.disabled = false;
  }
}



function extractActivityInfo(card) {
    let lat = parseFloat(card.dataset.lat);
    let lng = parseFloat(card.dataset.lng);
    
    // Fallback se le coordinate non sono nel dataset (es. carte vecchie o non aggiornate)
    if (isNaN(lat) || isNaN(lng)) {
        console.warn('extractActivityInfo: coordinate mancanti, uso fallback.', {
            place_id: extractPlaceId(card),
            dataset: { lat: card.dataset.lat, lng: card.dataset.lng, address: card.dataset.address }
        });
        lat = 41.1171;
        lng = 16.8719;
    }

    // Prova ad estrarre la categoria dalla card o da un contenitore vicino
    let category = card.dataset?.category || card.getAttribute('data-category') || '';
    // Rileva categoria dall'icona SVG presente nel badge (hotel/ristorante/vini)
    try {
      const iconImg = card.querySelector('img[src*="/assets/"]');
      const src = iconImg ? iconImg.getAttribute('src') || '' : '';
      if (src.includes('hotel.svg')) category = 'hotel';
      else if (src.includes('vini.svg')) category = 'vini';
      else if (src.includes('ristorante.svg')) {
        // Distinzione minima: ristoranti/cucina_tipica
        const labelText = iconImg.parentElement?.nextElementSibling?.textContent?.toLowerCase() || '';
        if (/cucina\s*tipica/.test(labelText)) category = 'cucina_tipica';
        else if (/ristoranti/.test(labelText)) category = 'cucina_tipica';
        else category = category || 'cucina_tipica';
      }
    } catch (e) {}
    // Se disponibile, prova a leggere la categoria dal testo/badge della card (accanto all'icona)
    // Nota: cerchiamo esplicitamente etichette testuali comuni per evitare falsi positivi sul nome (es. "cantina" nel nome)
    try {
      const cardText = (card.innerText || '').toLowerCase();
      let labelCat = '';
      // Priorità: etichette esplicite
      if (/\bcucina\s*tipica\b|\bristoranti\b|\btrattorie\b|\bosterie\b|\bpizzerie\b/.test(cardText)) {
        labelCat = 'cucina_tipica';
      }else if (/\bdolci\b|\bpasticceri[ae]\b|\bdessert\b|\bgelateri[ae]\b/.test(cardText)) {
        labelCat = 'dolci tipici';
      
      } else if (/\bvini\b|\benoteca\b/.test(cardText)) {
        labelCat = 'vini';
      } else if (/\bhotel\b|\bstrutture\s*ricettive\b/.test(cardText)) {
        labelCat = 'hotel';
      } 
      if (labelCat) {
        category = labelCat;
      }
    } catch (e) {}
    // Se la categoria è "la_nostra_selezione" o non è valorizzata, prova i fallback di sezione
    if (!category || category === 'la_nostra_selezione') {
        const catContainer = card.closest('[data-category]');
        const rawCat = catContainer ? (catContainer.getAttribute('data-category') || '') : '';
        category = (rawCat && rawCat !== 'la_nostra_selezione') ? rawCat : '';
        if (!category) {
            // Fallback con classi di sezione note (ristoranti -> cucina_tipica)
            if (card.closest('.wines-section')) category = 'vini';
            else if (card.closest('.restaurants-section')) category = 'cucina_tipica';
            else if (card.closest('.dishes-section')) category = 'cucina_tipica';
            else if (card.closest('.desserts-section') || card.closest('.dolci-section')) category = 'dolci tipici';
            else if (card.closest('.hotels-section')) category = 'hotel';

        }
    }

    const info = {
        place_id: extractPlaceId(card),
        name: card.querySelector('h4, h3')?.innerText || '',
        address: card.dataset.address || '',
        rating: (function(){
            const dr = card.dataset && card.dataset.rating ? card.dataset.rating : '';
            if (dr) {
                const num = parseFloat(dr);
                return isNaN(num) ? dr : num;
            }
            const rt = card.querySelector('.rating')?.innerText || '';
            return rt;
        })(),
        reviews: (function(){
            const dv = card.dataset && card.dataset.reviews ? card.dataset.reviews : '';
            if (dv !== '') {
                const num = parseInt(dv, 10);
                return isNaN(num) ? dv : num;
            }
            return '';
        })(),
        image: card.querySelector('[style*="background-image"]')
               ?.style.backgroundImage.replace('url("','').replace('")','') || '',
		    location: { lat: lat, lng: lng },
        category: category
    };
    // Per coerenza con l'inserimento in LFW, imposta anche type
    try { info.type = category || ''; } catch (e) {}
    return info;
}


function importBackendSelection() {
  const cards = document.querySelectorAll('#page-selection .selection-card');
  console.log('importBackendSelection: cards trovate =', cards.length);
  const before = manualSelection.length;

  cards.forEach(card => {
    const act = extractActivityInfo(card);
    const hasCoords = act && act.location && typeof act.location.lat === 'number' && typeof act.location.lng === 'number';
    const hasId = !!act.place_id;
    if (!hasId) {
      console.warn('importBackendSelection: card senza place_id, skip.', card);
      return;
    }
    if (!hasCoords) {
      console.warn('importBackendSelection: card senza coordinate valide, uso fallback o skip.', act);
    }
    if (!manualSelection.some(item => item.place_id === act.place_id)) {
      manualSelection.push(act);
    }
  });

  console.log('importBackendSelection: aggiunti', manualSelection.length - before, 'elementi; totale =', manualSelection.length);
  if (window.mapManager && typeof window.mapManager.updateItinerary === 'function') {
    window.mapManager.updateItinerary(manualSelection);
  }
  if (typeof renderRouteList === 'function') {
    renderRouteList(manualSelection);
  }
}





/* function importBackendSelection() {
  const cards = document.querySelectorAll('#page-selection .selection-card');
  console.log('importBackendSelection: cards trovate =', cards.length);
  const before = manualSelection.length;

  cards.forEach(card => {
    const act = extractActivityInfo(card);
    const hasCoords = act && act.location && typeof act.location.lat === 'number' && typeof act.location.lng === 'number';
    const hasId = !!act.place_id;
    if (!hasId) {
      console.warn('importBackendSelection: card senza place_id, skip.', card);
      return;
    }
    if (!hasCoords) {
      console.warn('importBackendSelection: card senza coordinate valide, uso fallback o skip.', act);
    }
    if (!manualSelection.some(item => item.place_id === act.place_id)) {
      // Assicura che category/type siano valorizzati per gli elementi iniziali
      try {
        const cat = getActCategoryForLfw(act);
        if (cat) {
          if (!act.category || act.category === 'la_nostra_selezione') act.category = cat;
          if (!act.type) act.type = cat;
        }
      } catch (err) {}
      manualSelection.push(act);
    }
  });

  console.log('importBackendSelection: aggiunti', manualSelection.length - before, 'elementi; totale =', manualSelection.length);
  if (window.mapManager && typeof window.mapManager.orderActivitiesByDistance === 'function') {
    window.mapManager.orderActivitiesByDistance(manualSelection[0], manualSelection)
      .then(sortedActivities => {
        window.mapManager.updateItinerary(sortedActivities);
      });
  }
  if (typeof renderRouteList === 'function') {
    renderRouteList(manualSelection);
  }
  // Aggiorna la visibilità del bottone di salvataggio
  updateSaveItineraryButtonVisibility();
  // Sincronizza suggests: rimuovi ogni elemento presente in manualSelection
  try {
    if (Array.isArray(suggests) && Array.isArray(manualSelection)) {
      const selectedIds = new Set(manualSelection.map(a => a.place_id));
      suggests = suggests.filter(s => !selectedIds.has(s.place_id));
      const grid = document.getElementById('suggestions-grid');
      if (grid) {
        [...grid.querySelectorAll('.activity-card')].forEach(el => {
          const pid = el.getAttribute('data-place-id');
          if (selectedIds.has(pid)) el.remove();
        });
      }

      // Rimuovi dalla pagina LFW eventuali card/link che corrispondono a elementi già selezionati
      const lfw = document.getElementById('page-lfw');
      if (lfw) {
        // Rimuovi activity-card con data-place-id
        [...lfw.querySelectorAll('.activity-card')].forEach(el => {
          const pid = el.getAttribute('data-place-id');
          if (selectedIds.has(pid)) el.remove();
        });
        // Rimuovi link con href contenente place_id
        [...lfw.querySelectorAll('a[href*="place_id="]')].forEach(a => {
          const m = a.href.match(/place_id=([^&]+)/);
          const pid = m && m[1] ? m[1] : '';
          if (pid && selectedIds.has(pid)) a.remove();
        });
      }
    }
  } catch (e) {}
  // Autosalva cache dopo importazione della selezione dal backend
  try { maybeAutoSaveCityCache('backend'); } catch (e) {}
}

  */
 















function renderRouteList(activities) {
  const container = document.getElementById('route-list');
  if (!container) return;

  container.innerHTML = '';

  activities.forEach((act, index) => {
    const item = document.createElement('div');
    item.className = 'route-item';

    item.innerHTML = `
      <div class="flex-1 bg-white/10 rounded-xl p-3 hover:bg-white/20 transition">
        <h4 class="font-semibold text-sm">${act.name}</h4>
        <div class="text-xs opacity-80 mb-2">⭐ ${act.rating || '–'}</div>

        <button
          onclick="openActivityModal('${act.place_id}','${act.name}')"
          class="text-xs flex items-center gap-1 text-[#b7f056] hover:underline"
        >
          <span class="material-icons text-sm">visibility</span>
          Visualizza la scheda
        </button>
      </div>
    `;

    container.appendChild(item);
  });
}
 
 
 
 
 


function updateSelectionUI() {
    const grid = document.querySelector('#page-selection .selection-grid');
    if (!grid) return;

    grid.querySelectorAll('.selected-card').forEach(el => el.remove());

    const buildActivityLinkForSelection = (act) => {
        try {
            if (act.website) return act.website;
            const placeId = act.place_id;
            if (placeId && !String(placeId).startsWith('gemini-')) {
                return `https://www.google.com/maps/place/?q=place_id:${String(placeId)}`;
            }
            const name = act.name || '';
            const address = act.address || act.formatted_address || act.vicinity || '';
            const loc = act.location || {};
            const lat = loc.lat ?? loc.latitude ?? act.lat;
            const lng = loc.lng ?? loc.longitude ?? act.lng;
            const query = (name + ' ' + address).trim() || name || address;
            if (query) {
                return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
            }
            if (lat != null && lng != null) {
                const q = `${lat},${lng}`;
                return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`;
            }
            return 'https://www.google.com/maps';
        } catch (e) {
            return 'https://www.google.com/maps';
        }
    };

    manualSelection.forEach(act => {
        const card = document.createElement('div');
        const name = String(act.name || 'Nome non disponibile');
        const escapedNameAttr = name.replace(/'/g, '&#39;');
        const placeId = act.place_id || '';
        const rating = act.rating || 'N/A';
        const reviews = act.reviews || act.user_ratings_total || 'N/A';
        const priceLevel = act.price_level || 0;
        const price = priceLevel ? '€'.repeat(priceLevel) : '';
        const address = act.address || act.formatted_address || act.vicinity || 'Indirizzo non disponibile';
        const mapsUrl = buildActivityLinkForSelection(act);

        let category = '';
        try { category = (getActCategoryForLfw(act) || act.display_category || act.category || '').toLowerCase(); } catch (e) { category = ''; }

        const categoryDisplay = {
            'hotel': { svg: 'hotel.svg', name: 'Hotel', color: '' },
            'strutture ricettive': { svg: 'hotel.svg', name: 'Hotel', color: '' },
            'ristoranti': { svg: 'ristorante.svg', name: 'Ristoranti', color: '' },
            'dolci tipici': { svg: 'dolci.svg', name: 'Dolci Tipici', color: '' },
            'cucina_tipica': { svg: 'ristorante.svg', name: 'Cucina Tipica', color: '' },
            'vini': { svg: 'vini.svg', name: 'Vini', color: '' }
        };

        let svgIcon, displayName, catColor;
        if (category && categoryDisplay[category]) {
            svgIcon = categoryDisplay[category].svg;
            displayName = categoryDisplay[category].name;
            catColor = categoryDisplay[category].color;
        } else {
            svgIcon = 'ristorante.svg';
            displayName = category ? category.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) : 'Selezione';
            catColor = '';
        }

        const loc = act.location || {};
        const lat = loc.lat ?? loc.latitude ?? act.lat ?? '';
        const lng = loc.lng ?? loc.longitude ?? act.lng ?? '';
        const photoUrl = act.image || act.photo || act.photo_url || '';

        const imageHtml = photoUrl
            ? `<div class="activity-image" style="display:block; width: calc(100% + 20px); height: 200px; background-image: url(${photoUrl}); background-size: cover; background-position: center; border-top-left-radius: 12px; border-top-right-radius: 12px; margin: -10px -10px 12px -10px;"></div>`
            : '';

        card.className = 'activity-card selection-card selected-card';
        card.setAttribute('data-place-id', placeId);
        card.setAttribute('data-address', (address || '').replace(/"/g, '&quot;'));
        if (category) card.setAttribute('data-category', category);
        card.setAttribute('data-rating', rating);
        card.setAttribute('data-reviews', reviews);
        if (lat !== '') card.setAttribute('data-lat', lat);
        if (lng !== '') card.setAttribute('data-lng', lng);

        card.setAttribute('style',
            'border: 1px solid #e2e8f0; ' +
            'border-radius: 12px; ' +
            'padding: 10px; ' +
            'background: white; ' +
            'box-shadow: 0 2px 8px rgba(0,0,0,0.1); ' +
            'transition: transform 0.2s, box-shadow 0.2s; ' +
            'min-height: 380px; ' +
            'display: flex; ' +
            'flex-direction: column; ' +
            'justify-content: space-between; ' +
            'overflow: hidden; ' +
            'position: relative; ' +
            'cursor: pointer;'
        );

        card.setAttribute('onmouseenter', "this.style.transform='translateY(-4px)'; this.style.boxShadow='0 4px 16px rgba(0,0,0,0.15)'; try{this.querySelector('.minus-btn').style.opacity='1';}catch(e){}");
        card.setAttribute('onmouseleave', "this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.1)'; try{this.querySelector('.minus-btn').style.opacity='0';}catch(e){}");

        const priceHtml = price ? `<span style="color: #64748b; font-size: 0.875rem; margin-left: 4px;">${price}</span>` : '';

        card.innerHTML = `
            ${imageHtml}
            <button type="button" class="minus-btn" title="Rimuovi"
                data-place-id="${placeId}"
                style="position: absolute; top: 48px; right: 10px; width: 28px; height: 28px; border-radius: 9999px; border: 2px solid #0f3e34; color:#0f3e34; background: #ffffff; display: inline-flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700; cursor: pointer; opacity: 0; transition: opacity 0.2s; z-index: 2;"
                onmouseover="this.style.background='#b7f056'"
                onmouseout="this.style.background='#ffffff'">-</button>
            <span aria-hidden="true" style="position: absolute; top: 20px; right: 10px; width: 20px; height: 20px; border-radius: 9999px; background: #facc15; color: #22c55e; display: inline-flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 800; box-shadow: 0 0 0 2px #ffffff; z-index: 10000; pointer-events: none;">✓</span>
            <div style="padding: 14px 12px 12px 12px; display: flex; flex-direction: column; height: auto;">
                <div style="display: inline-flex; align-items: center; gap: 12px; font-size: 0.95rem; margin: 12px 0 8px; color: #374151; text-transform: uppercase; font-weight: 700; height: 36px;">
                    <span style="width: 32px; height: 32px; border-radius: 9999px; display: inline-flex; align-items: center; justify-content: center; background: ${catColor};">
                        <img src="/assets/${svgIcon}" alt="${displayName}" style="width: 24px; height: 24px;" />
                    </span>
                    <span style="font-weight: 700; letter-spacing: 0.02em;">${displayName.toUpperCase()}</span>
                </div>
                <h3 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 6px; line-height: 1.3; color: #1e293b;">
                    ${name} <span aria-hidden="true" style="color: #22c55e; font-weight: 800; font-size: 18px; margin-left: 8px;"></span>
                    ${priceHtml}
                </h3>
                <p style="margin-bottom: 8px; font-size: 0.875rem; color: #334155;"><b>⭐ ${rating}</b> · ${reviews} recensioni</p>
                <div style="margin-top: 4px;"></div>
                <div style="padding-top: 2px;">
                    <a href="${mapsUrl}" target="_blank" class="selection-card-link" onclick="openActivityModal('${placeId}', '${escapedNameAttr}'); return false;" style="display: inline-flex; align-items: center; gap: 6px; text-decoration: none; font-size: 0.875rem; font-weight: 600; color: #0f3e34;">Visualizza la scheda<span class="material-icons" style="font-size: 16px; line-height: 1; color: #0f3e34;">arrow_forward</span></a>
                </div>
            </div>
        `;

        grid.appendChild(card);
    });
	
	mapManager.orderActivitiesByDistance(manualSelection[0], manualSelection)
		.then(sortedActivities => {
			mapManager.updateItinerary(sortedActivities);
		});
	renderRouteList(manualSelection);

    // Chiudi l'overlay quando la pagina Selezione è popolata
    try {
        const activePage = (typeof getCurrentActivePage === 'function') ? getCurrentActivePage() : null;
        const hasCards = grid && grid.children && grid.children.length > 0;
        if (hasCards && (!activePage || activePage === 'selection')) { hideProgramLoading(); }
    } catch (e) {}
}


function dedupeOurSelection() {
    const grids = document.querySelectorAll('#page-selection .our-selection .selection-grid');
    grids.forEach(grid => {
        const seen = new Set();
        Array.from(grid.children).forEach(card => {
            const pid = card.getAttribute('data-place-id') || (card.querySelector('a[href*="place_id:"]')?.href.match(/place_id:([^&]+)/)?.[1]) || '';
            if (!pid) return;
            if (seen.has(pid)) { card.remove(); } else { seen.add(pid); }
        });
    });
}


























// Re-applica automaticamente le trasformazioni quando l'AI aggiunge/modifica nodi
function initResultsMutationObserver() {
  const container = document.getElementById('categorized-results-container');
  if (!container || container.__observerInitialized) return;
  const observer = new MutationObserver((mutations) => {
    // debounce semplice
    clearTimeout(container.__transformTimer);
    container.__transformTimer = setTimeout(() => {
      try { applyAllResultTransformations(container); } catch (e) {}
    }, 50);
  });
  observer.observe(container, { childList: true, subtree: true });
  container.__observerInitialized = true;
}

function applyAllResultTransformations(rootEl) {
  if (!rootEl) return;
  // Riscrivi subito i placeholder immagini, così i transform successivi non bloccano il rewrite
  try { rewriteDishImagePlaceholders(rootEl); } catch (e) {}
  // Forza impilamento verticale delle macro-sezioni culinarie se l'HTML è in griglia 12-col

  // Allineamento card: gestito dentro le funzioni di trasformazione


  // Centra i titoli delle sezioni al centro della pagina

  // Dopo le trasformazioni, esegui nuovamente il rewrite per coprire nuovi nodi
  try { rewriteDishImagePlaceholders(rootEl); } catch (e) {}

}

// Impila verticalmente sezioni come "Primi Piatti Tipici", "Prodotti Tipici", "Vini", "Eventi"

// Helper: aumenta l'altezza minima di tutte le card di una sezione
function increaseSectionCardsHeight(rootEl, opts, minHeightPx) {
  if (!rootEl || !opts) return;
  const { sectionSelector, headingRegex } = opts;

  let section = null;
  if (sectionSelector) {
    section = rootEl.querySelector(sectionSelector);
  }
  if (!section && headingRegex) {
    const heading = Array.from(rootEl.querySelectorAll('h2, h3')).find(h => headingRegex.test(((h.textContent || '').trim())));
    section = heading ? heading.closest('div') : null;
  }
  if (!section) return;

  const grid = section.querySelector('.grid') || section;
  const cards = Array.from(grid.children).filter(el => el && el.nodeType === 1);
  if (!cards.length) return;

  const applyMinHeight = (els) => {
    els.forEach(el => {
      try {
        const cls = el.className || '';
        const cleaned = cls.replace(/(^|\s)(min-h-\S+|h-\S+)(?=\s|$)/g, '').replace(/\s+/g, ' ').trim();
        el.className = cleaned;
        el.style.height = 'auto';
        el.style.minHeight = `${minHeightPx}px`;
      } catch (e) {}
    });
  };

  applyMinHeight(cards);
  setTimeout(() => applyMinHeight(cards), 200);
  setTimeout(() => applyMinHeight(cards), 1200);
}

// Helper: aumenta l'altezza minima delle cards nella colonna sinistra di una sezione
function increaseLeftColumnCardsHeight(rootEl, opts, minHeightPx, options) {
  if (!rootEl || !opts) return;
  const { sectionSelector, headingRegex } = opts;

  // Trova il contenitore della sezione (priorità al selector esplicito, altrimenti via heading)
  let section = null;
  if (sectionSelector) {
    section = rootEl.querySelector(sectionSelector);
  }
  if (!section && headingRegex) {
    const heading = Array.from(rootEl.querySelectorAll('h2, h3')).find(h => headingRegex.test(((h.textContent || '').trim())));
    section = heading ? heading.closest('div') : null;
  }
  if (!section) return;

  const grid = section.querySelector('.grid') || section;
  const cards = Array.from(grid.children).filter(el => el && el.nodeType === 1);
  if (!cards.length) return;

  // Identifica la colonna sinistra usando i bounding rect
  const rects = cards.map(el => ({ el, rect: el.getBoundingClientRect() }));
  const minLeft = Math.min.apply(null, rects.map(r => r.rect.left));
  const leftColumn = rects
    .filter(r => Math.abs(r.rect.left - minLeft) < 5)
    .sort((a, b) => a.rect.top - b.rect.top)
    .map(r => r.el);

  const onlyFirstTwo = !options ? true : options.onlyFirstTwo !== false ? true : false;
  const targetCards = onlyFirstTwo ? leftColumn.slice(0, 2) : leftColumn;
  if (!targetCards.length) return;

  const applyMinHeight = (els) => {
    els.forEach(el => {
      try {
        const cls = el.className || '';
        const cleaned = cls.replace(/(^|\s)(min-h-\S+|h-\S+)(?=\s|$)/g, '').replace(/\s+/g, ' ').trim();
        el.className = cleaned;
        el.style.height = 'auto';
        el.style.minHeight = `${minHeightPx}px`;
      } catch (e) {}
    });
  };

  applyMinHeight(targetCards);
  setTimeout(() => applyMinHeight(targetCards), 200);
  setTimeout(() => applyMinHeight(targetCards), 1200);
}



// Riscrivi <img src="url_immagine"> con endpoint CSE basato sul nome del piatto
function rewriteDishImagePlaceholders(rootEl) {
  // Limita la riscrittura dei src alle immagini presenti nella pagina Intro
  const pageIntro = document.getElementById('page-intro');
  if (!pageIntro) return;
  const imgs = Array.from(pageIntro.querySelectorAll('img'));

  if (!imgs.length) return;

  // Risolvi la città con fallback: usa currentLocation, poi window.currentLocation, poi data-city dal body
  const cityName = (typeof currentLocation === 'string' && currentLocation.trim())
    ? currentLocation.trim()
    : (typeof window !== 'undefined' && typeof window.currentLocation === 'string' && window.currentLocation.trim())
      ? window.currentLocation.trim()
      : (document && document.body && document.body.dataset && document.body.dataset.city
          ? String(document.body.dataset.city).trim()
          : '');

  imgs.forEach(img => {
    try {
      const srcAttr = (img.getAttribute('src') || '').trim();
      // Salta se è già il nostro endpoint CSE
      if (/^\s*\/image_search_cse\?/i.test(srcAttr)) return;

      // Estrai il nome piatto dal contesto vicino
      let dish = '';
      const card = img.closest('.bg-white, .card, .place-card, .rounded-xl, div');
      if (card) {
        const h3 = card.querySelector('h3');
        if (h3) dish = (h3.textContent || '').trim();
      }
      if (!dish) {
        let sib = img.parentElement;
        let tries = 0;
        while (sib && tries < 3 && !dish) {
          const h3 = sib.querySelector ? sib.querySelector('h3') : null;
          if (h3) dish = (h3.textContent || '').trim();
          sib = sib.nextElementSibling;
          tries++;
        }
      }
      // Fallback: usa l'attributo alt se non è stato trovato nel contesto
      if (!dish) {
        const altText = (img.getAttribute('alt') || '').trim();
        if (altText) dish = altText;
      }
      // Ulteriore fallback: se è un placeholder con parametro ?text= ricava il nome piatto
      try {
        const lower = srcAttr.toLowerCase();
        if (!dish && (/via\.placeholder\.com/.test(lower) || /placeholder\.com/.test(lower))) {
          const qIndex = srcAttr.indexOf('?');
          if (qIndex !== -1) {
            const qs = srcAttr.substring(qIndex + 1);
            const params = new URLSearchParams(qs);
            const textParam = params.get('text');
            if (textParam) {
              dish = decodeURIComponent(textParam.replace(/\+/g, ' ')).trim();
            }
          }
        }
      } catch (e) {}
      if (!dish) return;

      // Decidi se riscrivere: placeholder, link locali, o fonti non-CSE (Wikipedia/Picsum/Pexels/Pixabay)
      const srcLower = srcAttr.toLowerCase();
      let shouldRewrite = (
        srcLower === 'url_immagine' ||
        /(^|\/)url_immagine(\?|$)/.test(srcLower) ||
        /^\s*\/image_search\?/i.test(srcLower) ||
        /^\s*\/image_proxy/i.test(srcLower) ||
        /via\.placeholder\.com/.test(srcLower) ||
        /placeholder\.com/.test(srcLower) ||
        /wikipedia\.org/.test(srcLower) ||
        /wikimedia\.org/.test(srcLower) ||
        /picsum\.photos/.test(srcLower) ||
        /pexels\.com/.test(srcLower) ||
        /pixabay\.com/.test(srcLower) ||
        // Escludi/riscrivi immagini provenienti da domini social
        /instagram\.com/.test(srcLower) ||
        /cdninstagram\.com/.test(srcLower) ||
        /instagr\.am/.test(srcLower) ||
        /facebook\.com/.test(srcLower) ||
        /fbcdn\.net/.test(srcLower) ||
        /tiktok\.com/.test(srcLower)
      );
      // Allarga la regola: se è un URL assoluto http(s) e abbiamo identificato il nome del piatto,
      // riscrivi comunque verso CSE per evitare link casuali non pertinenti
      if (!shouldRewrite) {
        const looksExternal = /^https?:\/\//.test(srcAttr);
        if (looksExternal && dish) {
          shouldRewrite = true;
        }
      }
      if (!shouldRewrite) return;

      const base = '/image_search_cse';
      const qDish = encodeURIComponent(dish);
      const qCity = cityName ? `&city=${encodeURIComponent(cityName)}` : '';
      const url = `${base}?dish=${qDish}${qCity}`;
      img.src = url;
      img.setAttribute('data-image-source', 'cse');
      if (!img.alt) img.alt = dish;
    } catch (e) {}
  });
}


   function ensureSelectionPanel() {
  const pageSelection = document.getElementById('page-selection');
  
  if (!pageSelection) return;

  // Se esiste già una selection-grid, non fare nulla
  const existingGrid = pageSelection.querySelector('.selection-grid');
  if (existingGrid) return;

  // Costruisci il pannello verde "La nostra selezione" con la griglia
  const container = document.createElement('div');
  container.className = 'mb-8 ml-10';

  const panel = document.createElement('div');
  panel.className = 'our-selection rounded-xl bg-[#0f3e34] p-4 shadow-lg';

  const header = document.createElement('div');
  header.className = 'flex items-center justify-between mb-4';
  try {
    const cityName = (typeof currentLocation === 'string' && currentLocation.trim()) ? currentLocation.trim() : '';
    header.innerHTML = `
      <h3 class="text-2xl font-semibold text-white">Il mio itinerario${cityName ? `: ${cityName}` : ''}</h3>
    `;
  } catch (e) {
    header.innerHTML = `
      <h3 class="text-2xl font-semibold text-white">Il mio itinerario</h3>
    `;
  }

  const grid = document.createElement('div');
  // Griglia responsiva come backend: auto-fit + minmax 230px
  grid.className = 'selection-grid';
  try {
    grid.style.display = 'grid';
    grid.style.gap = '28px 28px';
    grid.style.alignItems = 'stretch';
    grid.style.justifyContent = 'start';
    grid.style.gridTemplateColumns = 'repeat(auto-fit, minmax(230px, 1fr))';
  } catch (e) {}

  panel.appendChild(header);
  panel.appendChild(grid);
  container.appendChild(panel);
  pageSelection.appendChild(container);
}



// Mostra la pagina di default in modalità risultati:
// - Se c'è un itinerario/caricamento (manualSelection o ranked) → Selezione
// - Altrimenti → Intro
// Viene eseguito solo se l'utente NON ha ancora navigato esplicitamente
function maybeShowDefaultResultsPage() {
  try {
    const userNavigated = !!(window.__USER_NAV_ACTIVE__);
    const current = (typeof getCurrentActivePage === 'function') ? getCurrentActivePage() : null;
    if (userNavigated && current) return;

    const hasSelection = Array.isArray(window.manualSelection) && window.manualSelection.length > 0;
    const hasRanked = !!(window.lastRankedResults && Object.keys(window.lastRankedResults).length);
    const defaultPage = (hasSelection || hasRanked) ? 'selection' : 'intro';

    if (!current || current === 'intro') {
      if (typeof showResultsPage === 'function') showResultsPage(defaultPage);
    }
  } catch (e) {}
}



async function loadProgramFromBackend(programId) {
  try {
    const res = await fetch(`/api/program_details/${programId}`);
    const data = await res.json();
    console.debug('loadProgramFromBackend: programId=', programId, 'response=', data);
    if (!data || !data.success) {
      console.error('Errore program_details:', data && data.error);
      return;
    }

    ensureSelectionPanel();

    // Imposta la città corrente
    if (data.city_name) {
      try { localStorage.setItem('sitesense_current_location', data.city_name); } catch (e) {}
      window.currentLocation = data.city_name;
    }

    const locals = Array.isArray(data.locals) ? data.locals : [];
    if (!locals.length) {
      console.warn('loadProgramFromBackend: nessun locale nel programma ', programId);
    }





    // Arricchisci ogni place_id con dettagli (coordinate, foto, rating)
    const enriched = await Promise.all(
      locals.map(async (loc) => {
        try {
          const r = await fetch(`/api/place_details/${loc.place_id}`);
          const details = await r.json();
          const parseNum = (v) => {
          const n = typeof v === 'number' ? v : (v != null ? parseFloat(String(v)) : NaN);
         return Number.isFinite(n) ? n : null;
      };
          const lat = parseNum((loc && (loc.lat ?? loc.latitude)) ?? (loc && loc.location && loc.location.lat));
          const lng = parseNum((loc && (loc.lng ?? loc.longitude)) ?? (loc && loc.location && loc.location.lng));

          return {
            place_id: loc.place_id,
            name: loc.name || details.name || '',
            address: loc.address || details.formatted_address || '',
            type: loc.type || (Array.isArray(details.types) ? (details.types[0] || '') : ''),
            image: loc.image || loc.photo || '',
            rating: details.rating || '',
            reviews: details.user_ratings_total || '',
            location:(lat != null && lng != null) ? { lat, lng } : null
          };
          
        } catch (err) {
          console.warn('Dettagli place falliti per', loc.place_id, err);
          return {
            place_id: loc.place_id,
            name: loc.name || '',
            address: loc.address || '',
            type: loc.type || '',
            image:  loc.image || '',
            rating:loc.rating || '',
            reviews: loc.reviews || '',
            location: null
          };
        }
      })
    );
    console.debug('loadProgramFromBackend: enriched count=', enriched.length);

    // Popola manualSelection e aggiorna UI/mappa
    manualSelection = enriched;
    try { localStorage.setItem('manual_selection', JSON.stringify(enriched)); } catch (e) {}
    if (typeof updateSelectionUI === 'function') updateSelectionUI();
    if (window.mapManager && typeof window.mapManager.orderActivitiesByDistance === 'function') {
      window.mapManager.orderActivitiesByDistance(enriched[0], enriched)
        .then(sortedActivities => {
          window.mapManager.updateItinerary(sortedActivities);
        });
    }
    if (typeof renderRouteList === 'function') renderRouteList(enriched);
    if (typeof syncSelectionIndicators === 'function') syncSelectionIndicators();

    // Mostra UI risultati
    try {
      const homeHero = document.getElementById('home-hero');
      const resultsSection = document.getElementById('results-section');
      const chatRightPanel = document.getElementById('chat-right-panel');
      if (homeHero) homeHero.style.display = 'none';
      if (resultsSection) resultsSection.classList.remove('hidden');
      // Aggiorna visibilità pannello chat in base allo stato (risultati/caricamento)
      updateChatPanelVisibility();
      document.body.classList.remove('bg-[#0f3e34]');
      document.body.classList.add('bg-[#e8f6ef]');
    } catch (e) {}
    // Evita restore accidentali: pulisci il flag di ritorno alla selezione
    try { sessionStorage.removeItem('return_to_selection'); } catch (e) {}
    try { if (typeof initResultsNav === 'function') initResultsNav(); } catch (e) {}

    // 🔁 Ricarica il contenuto della Pagina 1 (intro) dal JSON salvato
    try {
      const p1 = await fetch(`/assets/saved_itineraries/page1_${programId}.json`);
      if (p1.ok) {
        const js = await p1.json();
        const html = (js && (js.page1_html || js.html)) || '';
        // Se il JSON salvato contiene la città, impostala come currentLocation
        try {
          const cityFromJson = js && (js.city || js.city_name || js.cityName);
          if (cityFromJson && typeof cityFromJson === 'string' && cityFromJson.trim()) {
            window.currentLocation = cityFromJson.trim();
            try { localStorage.setItem('sitesense_current_location', window.currentLocation); } catch (e) {}
            console.log('🗺️ Località impostata da JSON salvato:', window.currentLocation);
          }
        } catch (e) { console.warn('Impostazione currentLocation da JSON fallita:', e); }
        const pageIntro = document.getElementById('page-intro');
        if (pageIntro && html) {
          const contentSection = document.createElement('div');
          contentSection.className = 'w-full max-w-[1400px] ml-6 mr-0 mb-8 order-first';
          contentSection.innerHTML = `\n            <div class="content-response">\n              ${html}\n            </div>\n          `;
          // Rimuovi eventuali duplicati precedenti
          try {
            const duplicates = pageIntro.querySelectorAll('.content-response');
            duplicates.forEach(el => { if (el.parentNode) el.parentNode.remove(); });
          } catch (e) {}
          // Inserisci come primo blocco della pagina intro
          try { pageIntro.insertBefore(contentSection, pageIntro.firstChild); } catch (e) {}
          // Applica trasformazioni di layout ai contenuti ripristinati
          try { applyAllResultTransformations(contentSection); } catch (e) {}
          // Sposta il contenuto subito dopo l’introduzione della città (se presente)
          try {
            const cityIntro = pageIntro.querySelector('#city-intro-section');
            if (cityIntro && cityIntro.parentNode === pageIntro) {
              pageIntro.insertBefore(contentSection, cityIntro.nextSibling);
            }
          } catch (e) {}
          // Imposta flag per indicare ripristino intro
          try { window.__RESTORED_PAGE1__ = true; } catch (e) {}
          // Mostra la pagina intro solo se non c'è navigazione utente o pagina attiva diversa
          try { maybeShowDefaultResultsPage(); } catch (e) {}
          // Aggiorna icone attive
          try {
            const iconsNav = document.getElementById('results-icons');
            if (iconsNav) {
              const btns = iconsNav.querySelectorAll('button[data-page]');
              btns.forEach(b => {
                const img = b.querySelector('img');
                const defaultSrc = b.dataset.iconDefault;
                const activeSrc = b.dataset.iconActive;
                if (!img || !defaultSrc || !activeSrc) return;
                const isActive = b.getAttribute('data-page') === 'intro';
                img.src = isActive ? activeSrc : defaultSrc;
              });
            }
          } catch (e) {}
        } else {
          // Se non c'è HTML salvato, mostra la pagina intro solo se appropriato
          try { maybeShowDefaultResultsPage(); } catch (e) {}
        }
      } else {
        // File non presente -> mostra la pagina intro solo se appropriato
        try { maybeShowDefaultResultsPage(); } catch (e) {}
      }
    } catch (e) {
      console.warn('Ripristino pagina 1 fallito:', e);
      try { if (typeof showResultsPage === 'function') showResultsPage('selection'); } catch (err) {}
    }

    // 🔁 Ricarica il contenuto della Pagina 3 (locals) dal JSON salvato
    try {
      const p3 = await fetch(`/assets/saved_itineraries/page3_${programId}.json`);
      if (p3.ok) {
        const js3 = await p3.json();
        const ranked = (js3 && (js3.ranked || js3.page3_ranked)) || null;
        if (ranked && typeof ranked === 'object' && Object.keys(ranked).length) {
          try { window.lastRankedResults = ranked; } catch (e) {}
          try { ensureSelectionPanel(); } catch (e) {}
          try { processAndDisplayMap({ tool_name: 'search_google_maps', tool_data: ranked }); } catch (e) {}
        }
      }
    } catch (e) {
      console.warn('Ripristino pagina 3 fallito:', e);
    }
  } catch (error) {
    console.error('Errore nel caricamento del programma:', error);
  }
}

// Avvio automatico su /program/{id}
function clearRestoreSnapshots() {
  try {
    sessionStorage.removeItem('restore_results');
    ['snapshot_map_wrapper','snapshot_categorized','snapshot_map','snapshot_chat_right','snapshot_chat_messages','snapshot_message_history','snapshot_manual_selection','snapshot_page_intro','snapshot_page_selection','snapshot_page_lfw','snapshot_page_map']
      .forEach(k => sessionStorage.removeItem(k));
  } catch (e) {}
}
document.addEventListener('DOMContentLoaded', () => {
  try {
    const pid = window.__RESTORE_PROGRAM_ID__ || getProgramIdFromPath();
    if (pid) {
      // Ricorda la pagina attiva prima di avviare il caricamento
      let __ACTIVE_PAGE_BEFORE_LOAD__ = null;
      try { __ACTIVE_PAGE_BEFORE_LOAD__ = (typeof getCurrentActivePage === 'function') ? getCurrentActivePage() : null; } catch (e) {}
      try { sessionStorage.removeItem('return_to_selection'); } catch (e) {}
      try { clearRestoreSnapshots(); } catch (e) {}
      enterResultsMode(); // nasconde home, mostra risultati
      // Mostra animazione di caricamento per la pagina Programma
      try { showProgramLoading(); } catch (e) {}
      loadProgramFromBackend(pid).then(() => {
        // Lascia che la funzione decida la pagina, senza forzare "Intro" se l'utente è su un'altra pagina
        if (!window.__RESTORED_PAGE1__) {
          try { maybeShowDefaultResultsPage(); } catch (e) {}
        }
        try { if (typeof initResultsNav === 'function') initResultsNav(); } catch (e) {}
        // Auto-avanzamento su scroll e observer disattivati su richiesta
        // Esegui una riscrittura globale dei placeholder immagini dopo il caricamento
        try { rewriteDishImagePlaceholders(document.body); } catch (e) {}
        setTimeout(() => { try { rewriteDishImagePlaceholders(document.body); } catch (e) {} }, 150);
        setTimeout(() => { try { rewriteDishImagePlaceholders(document.body); } catch (e) {} }, 800);
      }).finally(() => {
        // Nascondi animazione di caricamento
        try { hideProgramLoading(); } catch (e) {}
        // Ripristina la pagina attiva pre-caricamento se presente (evita switch a Intro)
        try {
          const wanted = __ACTIVE_PAGE_BEFORE_LOAD__;
          if (wanted && typeof showResultsPage === 'function') {
            // Consenti lo switch programmato per preservare la pagina corrente
            try { window.__USER_NAV_ACTIVE__ = true; } catch (e) {}
            showResultsPage(wanted);
          }
        } catch (e) {}

        // Messaggio di benvenuto in Programma di viaggio
        try {
          const city = window.currentLocation || localStorage.getItem('sitesense_current_location') || '';
          const msg = city ? (`Benvenuto nel tuo Programma di viaggio a ${city}. Posso aiutarti con info, indicazioni e dettagli!`) :
                             ('Benvenuto nel tuo Programma di viaggio. Posso aiutarti con info, indicazioni e dettagli!');
          window.__CHAT_TOGGLE_VISIBLE__ = true;
          try { ensureChatToggle(); } catch (e) {}
          updateChatPanelVisibility();
          addChatbotMessage(msg, false);
        } catch (e) { console.warn('Welcome message non inviato:', e); }
      });
    }
  } catch (e) {
    console.error('Ripristino programma fallito:', e);
  }
});

function enterResultsMode() {
  document.body.classList.add('results-mode');
  try {
    document.body.classList.remove('bg-[#0f3e34]');
    document.body.classList.remove('bg-[#e8f6ef]');
    document.body.classList.remove('body-map-active');
    document.body.classList.remove('body-selection-active');
    // In modalità risultati: riabilita lo scroll globale
    document.body.classList.remove('body-home-hero');
  } catch (e) {}

  // In modalità risultati, mostra il logo header
  try {
    const brandLogo = document.getElementById('brand-logo-header');
    if (brandLogo) brandLogo.style.display = '';
  } catch (e) {}

  const homeHero = document.getElementById('home-hero');
  const resultsSection = document.getElementById('results-section');
  const mapWrapper = document.getElementById('map-wrapper');
  const chatRightPanel = document.getElementById('chat-right-panel');
  const chatRightForm = document.getElementById('chat-right-form');
  const searchForm = document.getElementById('search-form');

  if (homeHero) homeHero.style.display = 'none';
  if (resultsSection) resultsSection.classList.remove('hidden');
  if (mapWrapper) mapWrapper.classList.add('hidden');
  // Mostra il pannello chat solo quando i risultati sono visibili e non si sta caricando
  // Chat nascosta di default in modalità risultati
  window.__CHAT_TOGGLE_VISIBLE__ = false;
  try { ensureChatToggle(); } catch (e) {}
  updateChatPanelVisibility();

  // Footer risultati attivo: mostra il copyright in modalità risultati
  try {
    const resultsFooter = document.getElementById('results-footer');
    if (resultsFooter) resultsFooter.classList.remove('hidden');
  } catch (e) {}

  // Nascondi il copyright in alto nelle pagine risultati
  try {
    const topCopyright = document.getElementById('home-top-copyright');
    if (topCopyright) {
      topCopyright.classList.add('hidden');
      topCopyright.style.display = 'none';
    }
  } catch (e) {}

  // Sposta l'unico form nello slot dei risultati (in basso a destra)
  try { moveSearchFormToSlot('results-form-slot'); } catch (e) {}

  // Nascondi badge/icone cookie in modalità risultati
  try {
    document.querySelectorAll('#iubenda-cs-container, #iubenda-cs-embedded, .iubenda-cs-badge, .iubenda-iframe, [class*="iubenda"], [id*="iubenda"]').forEach(function(el){
      if (el && el.tagName && el.tagName.toLowerCase() !== 'script') {
        el.style.display = 'none';
        el.style.visibility = 'hidden';
      }
    });
  } catch (e) {}

  // Aggiorna la visibilità del pannello e della barra chat nei risultati
  try { updateChatPanelVisibility(); } catch (e) {}

   ensureSelectionPanel();

 try { if (typeof initResultsNav === 'function') initResultsNav(); } catch (e) {}
 // Non sovrascrivere la pagina attiva quando si entra in modalità risultati
 try { maybeShowDefaultResultsPage(); } catch (e) {}
  // Assicura visibilità corretta del pannello chat dopo l’entrata in risultati
  updateChatPanelVisibility();
  try { updateChatToggleVisibility(); } catch (e) {}
  // Auto-avanzamento su scroll e observer disattivati su richiesta
}

// In home (nessun programma attivo), mantieni footer nascosto e lascia scroll di pagina attivo
document.addEventListener('DOMContentLoaded', () => {
  try {
    const pid = window.__RESTORE_PROGRAM_ID__ || (typeof getProgramIdFromPath === 'function' ? getProgramIdFromPath() : null);
    if (!pid) {
      const resultsFooter = document.getElementById('results-footer');
      if (resultsFooter) resultsFooter.classList.add('hidden');
    }
  } catch (e) {}
});

// Attiva la modalità chatbot visibile nella pagina Programma di viaggio
// non appena i risultati sono pronti (niente overlay di caricamento)
// [Rimosso] Forzatura visibilità chat in pagina programma dopo caricamento risultati

// Animazione di caricamento per la pagina Programma di viaggio
  function showProgramLoading(options) {
  try {
    const opts = (options && typeof options === 'object') ? options : {};
    const nonBlocking = !!opts.nonBlocking;
    const labelText = opts.label || 'Caricamento itinerario...';
    // Se l'overlay esiste già, aggiorna etichetta e comportamento senza ricrearlo
    const existing = document.getElementById('program-loader');
    if (existing) {
      try {
        existing.style.pointerEvents = nonBlocking ? 'none' : 'auto';
        const labelEl = existing.querySelector('#program-loader-label');
        if (labelEl) labelEl.textContent = labelText;
        // Opacizza la pagina Selezione solo se overlay è bloccante
        const pageSelection = document.getElementById('page-selection');
        if (pageSelection) pageSelection.style.opacity = nonBlocking ? '' : '0';
        // Nascondi pannello chat durante overlay
        const chatRightPanel = document.getElementById('chat-right-panel');
        if (chatRightPanel) {
          chatRightPanel.classList.add('hidden');
          chatRightPanel.style.display = 'none';
        }
        const searchForm = document.getElementById('search-form');
        const resultsFormSlot = document.getElementById('results-form-slot');
        const chatFormContainer = document.getElementById('chat-right-form-container');
        if (searchForm) searchForm.style.display = 'none';
        if (resultsFormSlot) resultsFormSlot.style.display = 'none';
        if (chatFormContainer) chatFormContainer.style.display = 'none';
      } catch (e) {}
      return;
    }
    const overlay = document.createElement('div');
    overlay.id = 'program-loader';
    overlay.setAttribute('aria-live', 'polite');
    overlay.setAttribute('role', 'status');
    overlay.style.position = 'fixed';
    overlay.style.inset = '0';
    overlay.style.background = 'rgba(15,62,52,0.85)';
    overlay.style.display = 'flex';
    overlay.style.flexDirection = 'column';
    overlay.style.alignItems = 'center';
    overlay.style.justifyContent = 'center';
    overlay.style.zIndex = '9999';
    // Rendi l'overlay non bloccante se richiesto
    overlay.style.pointerEvents = nonBlocking ? 'none' : 'auto';

    const spinner = document.createElement('div');
    spinner.style.width = '66px';
    spinner.style.height = '66px';
    spinner.style.border = '6px solid #b8f36d';
    spinner.style.borderTopColor = 'transparent';
    spinner.style.borderRadius = '50%';
    spinner.style.animation = 'program-spin 0.9s linear infinite';

  const label = document.createElement('div');
  label.id = 'program-loader-label';
  label.textContent = labelText;
  label.style.marginTop = '14px';
  label.style.color = '#b8f36d';
  label.style.fontSize = '16px';
  label.style.fontWeight = '600';

  overlay.appendChild(spinner);
  overlay.appendChild(label);
  // Copyright rimosso dagli overlay di caricamento (pagine 2 e 3)
  document.body.appendChild(overlay);

  // Nascondi il pannello del chatbot durante la pagina di caricamento programma
  try {
    const chatRightPanel = document.getElementById('chat-right-panel');
    if (chatRightPanel) {
      chatRightPanel.classList.add('hidden');
      chatRightPanel.style.display = 'none';
    }
  } catch (e) {}

  // Nascondi anche la barra della chat/form durante il caricamento programma
  try {
    const searchForm = document.getElementById('search-form');
    const resultsFormSlot = document.getElementById('results-form-slot');
    const chatFormContainer = document.getElementById('chat-right-form-container');
    if (searchForm) searchForm.style.display = 'none';
    if (resultsFormSlot) resultsFormSlot.style.display = 'none';
    if (chatFormContainer) chatFormContainer.style.display = 'none';
  } catch (e) {}

  // Nascondi il copyright in alto durante la pagina di caricamento programma
  try {
    const topCopyright = document.getElementById('home-top-copyright');
    if (topCopyright) {
      topCopyright.classList.add('hidden');
      topCopyright.style.display = 'none';
    }
  } catch (e) {}

    // Registra l’animazione solo una volta
    if (!document.getElementById('program-loader-style')) {
      const style = document.createElement('style');
      style.id = 'program-loader-style';
      style.textContent = '@keyframes program-spin { to { transform: rotate(360deg); } }';
      document.head.appendChild(style);
    }

    // Nascondi temporaneamente il pannello “Il mio itinerario” SOLO se overlay è bloccante
    try {
      const pageSelection = document.getElementById('page-selection');
      if (pageSelection && !nonBlocking) pageSelection.style.opacity = '0';
    } catch (e) {}
  } catch (e) {}
}

function hideProgramLoading() {
  try {
    const overlay = document.getElementById('program-loader');
    if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
    // Ripristina la visibilità del pannello “Il mio itinerario”
    try {
      const pageSelection = document.getElementById('page-selection');
      if (pageSelection) pageSelection.style.opacity = '';
    } catch (e) {}
    // Aggiorna la visibilità del pannello chat al termine del caricamento
    updateChatPanelVisibility();
  } catch (e) {}
}

function isBlockedImageUrl(u) {
  try {
    const h = new URL(u, location.origin).hostname.toLowerCase();
    const domains = ["facebook.com","fbcdn.net","m.facebook.com","fbsbx.com","instagram.com","cdninstagram.com","instagr.am","tiktok.com"];
    return domains.some(d => h === d || h.endsWith("." + d));
  } catch (e) {
    return /facebook\.com|fbcdn\.net|m\.facebook\.com|fbsbx\.com|instagram\.com|cdninstagram\.com|instagr\.am|tiktok\.com/i.test(String(u || ""));
  }
}

const __FALLBACK_IMG__ = "/assets/Immagine_al_momento_non_disponibile_1__10_8__00217.webp";

function ensureImageLoaderStyles() {
  if (!document.getElementById("image-loader-style")) {
    const s = document.createElement("style");
    s.id = "image-loader-style";
    s.textContent =
      ".image-loader{position:relative}" +
      ".image-loader-overlay{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.08)}" +
      ".image-loader-overlay.left{justify-content:flex-start;padding-left:8px}" +
      ".image-loader-spinner{width:24px;height:24px;border:3px solid #16a34a;border-top-color:transparent;border-radius:50%;animation:img-spin .8s linear infinite}" +
      "@keyframes img-spin{to{transform:rotate(360deg)}}";
    document.head.appendChild(s);
  }
}

function addImageOverlay(container) {
  ensureImageLoaderStyles();
  if (!container) return null;
  try {
    const cs = window.getComputedStyle(container);
    if (cs.position === "static") container.style.position = "relative";
  } catch (e) {}
  container.classList.add("image-loader");
  const ov = document.createElement("div");
  ov.className = "image-loader-overlay";
  try {
    const w = container.clientWidth || 0;
    const h = container.clientHeight || 0;
    if (Math.min(w, h) && Math.min(w, h) <= 220) {
      ov.classList.add("left");
    }
  } catch (e) {}
  const sp = document.createElement("div");
  sp.className = "image-loader-spinner";
  ov.appendChild(sp);
  container.appendChild(ov);
  return ov;
}

function processImgElement(img) {
  try {
    if (!img || img.dataset.loaderBound === "1") return;
    img.dataset.loaderBound = "1";
    const container = img.parentElement || img;
    const ov = addImageOverlay(container);
    let src = img.getAttribute("src") || "";
    if (!src || isBlockedImageUrl(src)) {
      src = __FALLBACK_IMG__;
      try { img.setAttribute("src", src); } catch (e) {}
    }
    const cleanup = () => { try { if (ov) ov.remove(); } catch (e) {} };
    if (img.complete && img.naturalWidth > 0) { cleanup(); return; }
    img.addEventListener("load", cleanup, { once: true });
    img.addEventListener("error", () => {
      try { img.setAttribute("src", __FALLBACK_IMG__); } catch (e) {}
      cleanup();
    }, { once: true });
  } catch (e) {}
}

function extractBackgroundImageUrl(el) {
  try {
    const bg = el.style && el.style.backgroundImage ? el.style.backgroundImage : "";
    const m = bg.match(/url\((?:\"|')?(.*?)(?:\"|')?\)/i);
    return m ? m[1] : "";
  } catch (e) {
    return "";
  }
}

function processBgImageElement(el) {
  try {
    if (!el || el.dataset.loaderBound === "1") return;
    el.dataset.loaderBound = "1";
    const url = extractBackgroundImageUrl(el);
    const ov = addImageOverlay(el);
    try { el.style.backgroundImage = "none"; } catch (e) {}
    let target = url;
    if (!target || isBlockedImageUrl(target)) target = __FALLBACK_IMG__;
    const tmp = new Image();
    tmp.onload = () => {
      try { el.style.backgroundImage = `url("${target}")`; } catch (e) {}
      try { if (ov) ov.remove(); } catch (e) {}
    };
    tmp.onerror = () => {
      try { el.style.backgroundImage = `url("${__FALLBACK_IMG__}")`; } catch (e) {}
      try { if (ov) ov.remove(); } catch (e) {}
    };
    tmp.src = target;
  } catch (e) {}
}

function initImageLoaders(root) {
  try {
    const pageIntro = document.getElementById('page-intro');
    if (!pageIntro) return;
    const scope = (root && root.querySelectorAll && pageIntro.contains(root)) ? root : pageIntro;
    scope.querySelectorAll("img").forEach(processImgElement);
    scope.querySelectorAll('[style*="background-image"]').forEach(processBgImageElement);
  } catch (e) {}
}

function setupImageLoadObserver() {
  try {
    const pageIntro = document.getElementById('page-intro');
    if (!pageIntro) return;
    initImageLoaders(pageIntro);
    const obs = new MutationObserver((mutations) => {
      for (const m of mutations) {
        for (const node of m.addedNodes) {
          if (!(node instanceof Element)) continue;
          if (pageIntro.contains(node)) initImageLoaders(node);
        }
      }
    });
    obs.observe(pageIntro, { childList: true, subtree: true });
  } catch (e) {}
}

function initVoiceMinimal(){try{var mic=document.getElementById('mic-button');var input=document.getElementById('search-input');var form=document.getElementById('search-form');if(!mic||!input||!form)return;var SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){try{mic.style.display='none';}catch(e){}return;}var recognition=new SR();recognition.continuous=false;recognition.interimResults=true;recognition.lang='it-IT';var recognizing=false;mic.addEventListener('click',function(ev){if(recognizing){try{recognition.stop();}catch(e){}return;}try{recognition.start();}catch(e){}});recognition.onstart=function(){recognizing=true;};recognition.onerror=function(){recognizing=false;};recognition.onend=function(){recognizing=false;try{var val=(input.value||'').trim();if(val){var ev=new Event('submit',{bubbles:true,cancelable:true});ev.searchTerm=val;form.dispatchEvent(ev);}}catch(e){}};recognition.onresult=function(event){var interim='';var final='';for(var i=event.resultIndex;i<event.results.length;i++){var t=event.results[i][0].transcript;if(event.results[i].isFinal){final+=t;}else{interim+=t;}}input.value=(final||interim||'');};}catch(e){}}function capitalize(s){
  return String(s || '').replace(/\S/, function(m){ return m.toUpperCase(); });
}

document.addEventListener("DOMContentLoaded", () => {
  try { setupImageLoadObserver(); } catch (e) {}
  try { initVoiceMinimal(); } catch (e) {}
});

// Riallinea form e pannello chat quando cambia la larghezza della finestra
try {
    let __resizeTimer;
    window.addEventListener('resize', () => {
        try { clearTimeout(__resizeTimer); } catch (e) {}
        __resizeTimer = setTimeout(() => {
            try { ensureChatToggle(); } catch (e) {}
            try { updateChatPanelVisibility(); } catch (e) {}
            if (searchForm) searchForm.style.display = 'block';
            try { if (window.innerWidth <= 558) moveSearchFormToSlot('results-form-slot'); } catch (e) {}
        }, 120);
    });
} catch (e) {}
