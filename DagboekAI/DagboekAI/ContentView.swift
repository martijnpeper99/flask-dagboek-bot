import SwiftUI

struct ContentView: View {
    @Binding var dagboekVerslagMartijn: String
    @Binding var dagboekVerslagLisa: String

    let fetchDiaryEntry: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Dagboek AI")
                .font(.largeTitle)
                .padding()

            Text("Verslag Martijn:")
                .font(.headline)
            Text(dagboekVerslagMartijn)
                .padding()
                .multilineTextAlignment(.leading)

            Text("Verslag Lisa:")
                .font(.headline)
            Text(dagboekVerslagLisa)
                .padding()
                .multilineTextAlignment(.leading)

            Button("Genereer Dagboekverslagen Nu") {
                fetchDiaryEntry()
            }
            .padding()
            .background(Color.blue)
            .foregroundColor(.white)
            .cornerRadius(10)

            Spacer()
        }
        .padding()
    }
}
