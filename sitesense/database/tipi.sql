CREATE TABLE IF NOT EXISTS types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    typology VARCHAR(255)
);

INSERT INTO types (id, typology) VALUES
    (1, 'Hotel'),
    (2, 'Vini'),
    (3, 'Ristoranti');

SELECT * FROM types;