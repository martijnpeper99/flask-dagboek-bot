import SwiftUI

struct ContentView: View {
    @State private var dagboekVerslag: String = "Nog geen verslag opgehaald."

    var body: some View {
        VStack {
            Text("Dagboek AI")
                .font(.largeTitle)
                .padding()

            Text(dagboekVerslag)
                .padding()
                .multilineTextAlignment(.leading)

            Button("Genereer Dagboekverslag") {
                fetchDiaryEntry()
            }
            .padding()
            .background(Color.blue)
            .foregroundColor(.white)
            .cornerRadius(10)
        }
        .padding()
    }

    // ✅ Functie om dagboekverslag op te halen
    func fetchDiaryEntry() {
        guard let url = URL(string: "https://flask-dagboek-bot-production.up.railway.app/generate_diary_now") else {
            dagboekVerslag = "❌ Fout: Ongeldige URL."
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        URLSession.shared.dataTask(with: request) { data, response, error in
            guard let data = data, error == nil else {
                DispatchQueue.main.async {
                    dagboekVerslag = "❌ Fout bij ophalen: \(error?.localizedDescription ?? "Onbekende fout")"
                }
                return
            }

            do {
                let jsonResponse = try JSONSerialization.jsonObject(with: data, options: []) as? [String: Any]
                if let entry = jsonResponse?["entry"] as? String {
                    DispatchQueue.main.async {
                        dagboekVerslag = entry
                    }
                } else {
                    DispatchQueue.main.async {
                        dagboekVerslag = "❌ Geen dagboekverslag ontvangen."
                    }
                }
            } catch {
                DispatchQueue.main.async {
                    dagboekVerslag = "❌ JSON-fout: \(error.localizedDescription)"
                }
            }
        }.resume()
    }
}
