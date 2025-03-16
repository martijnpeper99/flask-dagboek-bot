import SwiftUI

@main
struct DagboekAIApp: App {
    @State private var dagboekVerslagMartijn: String = "Nog geen verslag (Martijn)."
    @State private var dagboekVerslagLisa: String = "Nog geen verslag (Lisa)."

    init() {
        // Elke 24 uur
        startAutoDiary()
    }

    var body: some Scene {
        WindowGroup {
            ContentView(
                dagboekVerslagMartijn: $dagboekVerslagMartijn,
                dagboekVerslagLisa: $dagboekVerslagLisa,
                fetchDiaryEntry: fetchDiaryEntry
            )
        }
    }

    func startAutoDiary() {
        // 86400 seconden = 24 uur
        Timer.scheduledTimer(withTimeInterval: 86400, repeats: true) { _ in
            fetchDiaryEntry()
        }
    }

    func fetchDiaryEntry() {
        guard let url = URL(string: "https://flask-dagboek-bot-production.up.railway.app/generate_diary_now") else {
            dagboekVerslagMartijn = "❌ Fout: Ongeldige URL."
            dagboekVerslagLisa = "❌ Fout: Ongeldige URL."
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        URLSession.shared.dataTask(with: request) { data, response, error in
            // Check netwerkfouten
            guard let data = data, error == nil else {
                DispatchQueue.main.async {
                    dagboekVerslagMartijn = "❌ Fout bij ophalen: \(error?.localizedDescription ?? "Onbekende fout")"
                    dagboekVerslagLisa = "❌ Fout bij ophalen: \(error?.localizedDescription ?? "Onbekende fout")"
                }
                return
            }

            // Probeer JSON te parsen
            do {
                let jsonResponse = try JSONSerialization.jsonObject(with: data, options: []) as? [String: Any]
                
                if let martijnText = jsonResponse?["martijn_entry"] as? String,
                   let lisaText = jsonResponse?["lisa_entry"] as? String {
                    DispatchQueue.main.async {
                        dagboekVerslagMartijn = martijnText
                        dagboekVerslagLisa = lisaText
                    }
                } else if let errorMsg = jsonResponse?["error"] as? String {
                    DispatchQueue.main.async {
                        dagboekVerslagMartijn = "❌ Server-error: \(errorMsg)"
                        dagboekVerslagLisa = "❌ Server-error: \(errorMsg)"
                    }
                } else {
                    DispatchQueue.main.async {
                        dagboekVerslagMartijn = "❌ Geen dagboekverslag ontvangen."
                        dagboekVerslagLisa = "❌ Geen dagboekverslag ontvangen."
                    }
                }
            } catch {
                DispatchQueue.main.async {
                    dagboekVerslagMartijn = "❌ JSON-fout: \(error.localizedDescription)"
                    dagboekVerslagLisa = "❌ JSON-fout: \(error.localizedDescription)"
                }
            }
        }.resume()
    }
}
