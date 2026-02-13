import { useState } from 'react';
import { Button } from './Button';

export function ContactForm() {
  const [formData, setFormData] = useState({
    nome: '',
    email: '',
    attivita: '',
    messaggio: ''
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Form submitted:', formData);
    // Handle form submission
    alert('Grazie per il tuo interesse! Ti contatteremo presto.');
    setFormData({ nome: '', email: '', attivita: '', messaggio: '' });
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <input
          type="text"
          name="nome"
          placeholder="Nome"
          value={formData.nome}
          onChange={handleChange}
          required
          className="w-full px-6 py-4 border-2 border-gray-200 rounded-lg focus:border-[#004D43] focus:outline-none transition-colors"
        />
      </div>
      <div>
        <input
          type="email"
          name="email"
          placeholder="Email"
          value={formData.email}
          onChange={handleChange}
          required
          className="w-full px-6 py-4 border-2 border-gray-200 rounded-lg focus:border-[#004D43] focus:outline-none transition-colors"
        />
      </div>
      <div>
        <input
          type="text"
          name="attivita"
          placeholder="Attività"
          value={formData.attivita}
          onChange={handleChange}
          required
          className="w-full px-6 py-4 border-2 border-gray-200 rounded-lg focus:border-[#004D43] focus:outline-none transition-colors"
        />
      </div>
      <div>
        <textarea
          name="messaggio"
          placeholder="Messaggio"
          value={formData.messaggio}
          onChange={handleChange}
          required
          rows={5}
          className="w-full px-6 py-4 border-2 border-gray-200 rounded-lg focus:border-[#004D43] focus:outline-none transition-colors resize-none"
        />
      </div>
      <Button type="submit" variant="primary">
        Invia richiesta
      </Button>
    </form>
  );
}
