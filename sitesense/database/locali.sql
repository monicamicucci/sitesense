CREATE TABLE locals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    program_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    address VARCHAR(255),
    type_id INT NOT NULL,
    place_id VARCHAR(128),
    lat DOUBLE,
    lng DOUBLE,
    image VARCHAR(512),
    rating DECIMAL(3,1),
    
	  FOREIGN KEY (program_id)
        REFERENCES programs(id)
        ON DELETE CASCADE,
		FOREIGN KEY (type_id)
        REFERENCES types(id)
        ON DELETE CASCADE
);


INSERT INTO locals (id, program_id, name, address, type_id, place_id, lat, lng, image, rating) VALUES
    (1, 1, 'Hotel A', 'Via Roma 123, Milano', 1, NULL, NULL, NULL, NULL, NULL),
    (2, 1, 'Hostel B', 'Via Milano 456, Milano', 1, NULL, NULL, NULL, NULL, NULL),
    (3, 2, 'Hotel C', 'Via Napoli 789, Napoli', 1, NULL, NULL, NULL, NULL, NULL);

  SELECT * FROM locals;