# In order to have everything from the ecosystem readily available, you'll just
# need to source the alias file. This is done automatically when using
# tmux/tmuxinator. If you don't use tmuxinator *or* when opening a new window
# inside the active tmux session, the following alias comes in handy:
alias srcecoalias='source ~/src/ledger-ecosystem/alias'

# Define the alias to start any Ledger interaction. One would usually have a
# decryption and/or mount command before starting the actual session (i.e.
# decrypt /path/to/folder && tmux start).
alias lpts='mux start ledger-private' # Ledger Privat Tmux Start
# Define the alias to stop any Ledger interaction. One would usually have an
# umount and/or an encryption and/or a backup command afterwards (i.e. kill
# tmux kill && encrypt /path/to/folder && backup /path/to/folder)
alias lptk='mux kill-session -t ledger-private' # Ledger Private Tmux Kill
