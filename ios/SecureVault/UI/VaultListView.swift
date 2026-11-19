import SwiftUI

struct VaultListView: View {
    @EnvironmentObject private var store: VaultStore
    @AppStorage(Prefs.sort) private var sortRaw = SortMode.nameAsc.rawValue
    @State private var query = ""
    @State private var adding = false
    @State private var showingSettings = false
    @State private var showingGenerator = false
    @State private var pendingDelete: Entry?

    private var sort: SortMode { SortMode(rawValue: sortRaw) ?? .nameAsc }

    var body: some View {
        NavigationStack {
            let visible = store.visible(query: query, sort: sort)
            List {
                ForEach(visible) { entry in
                    NavigationLink(value: entry.id) { EntryRow(entry: entry) }
                        .cardRow()
                        .swipeActions(edge: .leading) {
                            Button {
                                Task { await store.toggleFavourite(entry.name) }
                            } label: {
                                Label(entry.favourite ? "Unfavourite" : "Favourite",
                                      systemImage: entry.favourite ? "star.slash" : "star")
                            }
                            .tint(Theme.accent)
                        }
                        .swipeActions(edge: .trailing) {
                            Button(role: .destructive) { pendingDelete = entry } label: {
                                Label("Delete", systemImage: "trash")
                            }
                        }
                        .contextMenu {
                            Button { store.copy(entry.user, label: "Username") } label: {
                                Label("Copy username", systemImage: "person")
                            }
                            Button { store.copy(store.password(for: entry), label: "Password") } label: {
                                Label("Copy password", systemImage: "key")
                            }
                        }
                }
            }
            .listStyle(.insetGrouped)
            .themed()
            .overlay {
                if visible.isEmpty { emptyState }
            }
            .searchable(text: $query, prompt: "Search accounts")
            .navigationTitle("Accounts")
            .navigationDestination(for: UUID.self) { EntryDetailView(id: $0) }
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button { store.lock() } label: { Image(systemName: "lock.fill") }
                        .accessibilityLabel("Lock")
                }
                ToolbarItemGroup(placement: .navigationBarTrailing) {
                    Menu {
                        Picker("Sort", selection: $sortRaw) {
                            ForEach(SortMode.allCases) { Text($0.label).tag($0.rawValue) }
                        }
                        Divider()
                        Button { showingGenerator = true } label: {
                            Label("Password generator", systemImage: "wand.and.stars")
                        }
                        Button { showingSettings = true } label: {
                            Label("Settings", systemImage: "gearshape")
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                    Button { adding = true } label: { Image(systemName: "plus") }
                        .accessibilityLabel("Add account")
                }
            }
        }
        .sheet(isPresented: $adding) { EntryFormView(editing: nil) }
        .sheet(isPresented: $showingSettings) { SettingsView() }
        .sheet(isPresented: $showingGenerator) {
            NavigationStack { GeneratorView(onUse: nil) }
        }
        .confirmationDialog("Delete \(pendingDelete?.name ?? "")?",
                            isPresented: Binding(get: { pendingDelete != nil },
                                                 set: { if !$0 { pendingDelete = nil } }),
                            titleVisibility: .visible) {
            Button("Delete", role: .destructive) {
                if let name = pendingDelete?.name { Task { await store.delete(name) } }
            }
        } message: {
            Text("This removes the account from the vault on every device that uses it.")
        }
    }

    @ViewBuilder private var emptyState: some View {
        if query.isEmpty {
            VStack(spacing: 12) {
                Image(systemName: "key.horizontal").font(.system(size: 40)).foregroundStyle(Theme.muted)
                Text("No accounts yet").font(.headline)
                Button("Add your first account") { adding = true }
            }
        } else {
            Text("No accounts match “\(query)”.").foregroundStyle(Theme.secondaryText)
        }
    }
}

struct EntryRow: View {
    let entry: Entry

    var body: some View {
        HStack(spacing: 12) {
            Text(String(entry.name.prefix(1)).uppercased())
                .font(.headline)
                .frame(width: 36, height: 36)
                .background(Theme.primarySubtle, in: RoundedRectangle(cornerRadius: 8))
                .foregroundStyle(Theme.primary)
            VStack(alignment: .leading, spacing: 2) {
                Text(entry.name).font(.body.weight(.medium)).lineLimit(1)
                let subtitle = entry.user.isEmpty ? entry.url : entry.user
                if !subtitle.isEmpty {
                    Text(subtitle).font(.footnote).foregroundStyle(Theme.secondaryText).lineLimit(1)
                }
            }
            Spacer()
            if entry.favourite {
                Image(systemName: "star.fill").foregroundStyle(Theme.accent).font(.footnote)
            }
        }
        .padding(.vertical, 2)
    }
}
