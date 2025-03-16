import SwiftUI

@main
struct DagboekAIApp: App {
    @State private var dagboekVerslag: String = "Nog geen verslag opgehaald."

    init() {
        startAutoDiary()
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }

    func startAutoDiary() {
        Timer.scheduledTimer(withTimeInterval: 86400, repeats: true) { _ in
            fetchDiaryEntry()
        }
    }

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
