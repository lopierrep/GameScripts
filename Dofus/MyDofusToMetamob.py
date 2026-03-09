import csv

input_file = "mydofus_collection.csv"
output_file = "metamob_collection.csv"

with open(input_file, newline='', encoding="utf-8") as infile, \
     open(output_file, "w", newline='', encoding="utf-8") as outfile:

    reader = csv.DictReader(infile)
    writer = csv.writer(outfile)

    # Escribir encabezado nuevo
    writer.writerow(["Name", "Count"])

    for row in reader:
        name = row["Name"]
        count = row["Count"]
        writer.writerow([name, count])

print("Archivo convertido correctamente.")