import {
  Heart,
  Leaf,
  Sparkles,
  Award,
  Users,
  Calendar,
  Building2,
  Utensils,
  TrendingUp,
  Target,
  Globe,
} from "lucide-react";
import { Button } from "./components/Button";
import { IconCard } from "./components/IconCard";
import { PillarCard } from "./components/PillarCard";
import { CheckList } from "./components/CheckList";
import { ContactForm } from "./components/ContactForm";
import { ImageWithFallback } from "./components/figma/ImageWithFallback";

export default function App() {
  return (
    <div className="min-h-screen bg-[#EBFFF6]">
      {/* HERO SECTION */}
      <section className="relative h-[720px] flex items-center justify-center">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{
            backgroundImage: `linear-gradient(rgba(0, 0, 0, 0.4), rgba(0, 0, 0, 0.4)), url('https://images.unsplash.com/photo-1659907309594-4ef0ad0d25fa?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxpdGFsaWFuJTIwdmluZXlhcmQlMjBsYW5kc2NhcGV8ZW58MXx8fHwxNzY5MDg5MDgyfDA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral')`,
          }}
        />
        <div className="relative z-10 max-w-[1280px] mx-auto px-20 text-center">
          <h1 className="text-[64px] font-bold text-white mb-8 leading-tight">
            L'intelligenza artificiale che parla la lingua
            dell'Italia autentica
          </h1>
          <p className="text-xl text-white mb-12 max-w-[600px] mx-auto leading-relaxed">
            initalya è la speciale piattaforma con assistente
            virtuale AI multilingua dedicata al Made in Italy.
            Uno spazio digitale dove tecnologia e tradizione si
            fondono per generare itinerari di viaggio su misura,
            promuovere le attività locali e connettere realmente
            turisti e territori.
          </p>
          <div className="flex gap-4 justify-center">
            <Button variant="primary">
              Scopri come funziona
            </Button>
            <Button variant="light">Vieni initalya!</Button>
          </div>
        </div>
      </section>

      {/* VISION SECTION */}
      <section className="py-24 bg-[#EBFFF6]">
        <div className="max-w-[1280px] mx-auto px-20">
          <div className="grid grid-cols-2 gap-16 items-center">
            <div>
              <ImageWithFallback
                src="https://images.unsplash.com/photo-1760681556302-69e76e476b27?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxpdGFsaWFuJTIwY291bnRyeXNpZGUlMjB2aWxsYXxlbnwxfHx8fDE3NjkwODkwODN8MA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral"
                alt="Italian countryside"
                className="w-full h-[500px] object-cover rounded-2xl shadow-lg"
              />
            </div>
            <div>
              <h2 className="text-5xl font-bold text-[#004D43] mb-6">
                La nostra vision
              </h2>
              <h3 className="text-2xl font-medium text-[#004D43] mb-6">
                L'Italia più vera, a portata di tutti
              </h3>
              <p className="text-lg text-[#333333] leading-relaxed">
               
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* MISSION SECTION */}
      <section className="py-24 bg-white">
        <div className="max-w-[1280px] mx-auto px-20">
          <div className="text-center mb-16">
            <h2 className="text-5xl font-bold text-[#004D43] mb-6">
              La nostra mission
            </h2>
            <h3 className="text-2xl font-medium text-[#004D43] mb-6">
              Turisti e territori legati dal gusto
            </h3>
            <p className="text-lg text-[#333333] max-w-[800px] mx-auto leading-relaxed">
              Offriamo a turisti, viaggiatori, appassionati del settore enogastronomico, aziende B2B, ristoratori e istituzioni una piattaforma intelligente capace di incrociare esigenze e opportunità.
La nostra ambizione è semplice e potente: far dialogare il mondo con la vera essenza dell’Italia, attraverso la sua cucina, le sue storie e le sue persone.

            </p>
          </div>

          
        </div>
      </section>

      {/* PILASTRI SECTION */}
      <section className="py-24 bg-[#EBFFF6]">
        <div className="max-w-[1280px] mx-auto px-20">
          <h2 className="text-5xl font-bold text-[#004D43] text-center mb-16">
            I nostri pilastri
          </h2>
          <div className="grid grid-cols-4 gap-6">
            <PillarCard
              icon={Heart}
              title="Autenticità"
              description="Proponiamo esperienze reali, locali, non standardizzate, lontane dai circuiti turistici di massa. Ogni itinerario nasce dal territorio, dalle sue tradizioni e da chi le vive ogni giorno."
            />
            <PillarCard
              icon={Leaf}
              title="Sostenibilità"
              description="Sosteniamo le piccole realtà, i borghi e le risorse a km zero, contribuendo a un turismo che rispetta ed esalta ciò che rende l’Italia unica."
            />
            <PillarCard
              icon={Sparkles}
              title="Innovazione"
              description="Utilizziamo l’intelligenza artificiale, tecniche di storytelling e di digital marketing per reinventare il modo di conoscere l’Italia senza comprometterne la veridicità. "
            />
            <PillarCard
              icon={Award}
              title="Qualità"
              description="Selezioniamo con cura partner commerciali, media partner e collaborazioni, garantendo standard elevati e contenuti sempre affidabili e ispiranti."
            />
          </div>
                 
          
        </div>
      </section>

 {/* FRASE IN EVIDENZA */}
          <section className="mt-20 relative h-[320px] flex items-center justify-center">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{
            backgroundImage: `linear-gradient(rgba(0, 0, 0, 0.4), rgba(0, 0, 0, 0.4)), url('https://images.unsplash.com/photo-1514896856000-91cb6de818e0?q=80&w=1471&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D')`,
          }}
        />
        <div className=" relative z-10 max-w-[1280px] mx-auto px-20 text-center">
          <h3 className="text-[34px] font-bold text-white mb-8 leading-tight">
                <i>initalya è un ponte tra persone, culture e sapori, dove la tecnologia non sostituisce l’emozione, ma la amplifica.</i>
              </h3>
          <div className="flex gap-4 justify-center">
                      </div>
        </div>
      </section>

      {/* PARTNER CTA SECTION */}
      <section className="py-24 bg-[#004D43]">
        
        <div className="max-w-[980px] mx-auto px-20 text-center">
          <h2 className="text-5xl font-bold text-white mb-8">
            Scegli initalya per dare slancio e valore alla tua
            attività
          </h2>
          <p className="text-lg text-white mb-12 max-w-[900px] mx-auto leading-relaxed">
            Entra nel nostro circuito virtuoso,
sfrutta il canale più diretto per entrare in dialogo con i turisti di tutto il mondo! 
initalya è una piattaforma digitale che si rivela ottima come strumento strategico di marketing territoriale perché capace di valorizzare le realtà locali e di far maturare nuove opportunità per il turismo e l’economia. 
Nel nostro spazio si incontrano comuni ed enti pubblici sensibili all’innovazione, ristoranti e attività commerciali che vogliono farsi conoscere per le loro tipicità, strutture ricettive (hotel, agriturismi, B&B, resort, case vacanza) e organizzatori di eventi locali che si impegnano a creare relazioni, ricordi, ricchezza per i territori. 

          </p>
          <Button variant="light">Vieni initalya!</Button>
        </div>
      </section>

      {/* A CHI CI RIVOLGIAMO SECTION */}
      <section className="py-24 bg-[#EBFFF6]">
        <div className="max-w-[1280px] mx-auto px-20">
          <h2 className="text-5xl font-bold text-[#004D43] text-center mb-16">
            A chi ci rivolgiamo
          </h2>
          <div className="grid grid-cols-3 gap-8">
            <IconCard
              icon={Building2}
              title="Comuni ed enti pubblici"
              description="Per promuoversi in un ambiente digitale innovativo."
              variant="vertical"
            />
            <IconCard
              icon={Calendar}
              title="Organizzatori di eventi locali"
              description="che tengono vivo il tessuto sociale e turistico dei borghi"
              variant="vertical"
            />
            <IconCard
              icon={Utensils}
              title="Ristoratori, albergatori & produttori"
              description="che vogliono proporre il Made in Italy in modo coinvolgente"
              variant="vertical"
            />
          </div>
        </div>
      </section>

      {/* VANTAGGI PARTNER SECTION */}
      <section className="py-24 bg-white">
        <div className="max-w-[1280px] mx-auto px-20">
          <div className="grid grid-cols-2 gap-16 items-center">
            <div>
              <h2 className="text-5xl font-bold text-[#004D43] mb-12">
                I vantaggi di essere nostro partner
              </h2>
              <CheckList
                items={[
                  "Maggiore visibilità grazie all'assistente AI",
                  "Targeting intelligente basato sulle intenzioni di viaggio",
                  "Promozione multilingua automatica",
                  "Presenza negli itinerari personalizzati",
                  "Schede attività complete e aggiornate",
                  "Supporto al marketing territoriale",
                ]}
              />
            </div>
            <div>
              <ImageWithFallback
                src="https://images.unsplash.com/photo-1724232822245-f430d53466e0?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxhdXRoZW50aWMlMjBpdGFsaWFuJTIwcmVzdGF1cmFudHxlbnwxfHx8fDE3NjkwODkwODN8MA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral"
                alt="Italian restaurant"
                className="w-full h-[500px] object-cover rounded-2xl shadow-lg"
              />
            </div>
          </div>
        </div>
      </section>

      {/* CTA + FORM SECTION */}
      <section className="py-24 bg-[#EBFFF6]">
        <div className="max-w-[1280px] mx-auto px-20">
          <div className="grid grid-cols-2 gap-16">
            <div>
              <h2 className="text-5xl font-bold text-[#004D43] mb-6">
                Vuoi unirti a noi?
              </h2>
              <h3 className="text-2xl font-medium text-[#004D43]">
                Fatti trovare facilmente da chi cerca l’Italia più vera!
              </h3>
              </div>
            <div>
              <ContactForm />
            </div>
          </div>
        </div>
      </section>

      {/* TRANSIZIONE SECTION */}
    
    </div>
  );
}