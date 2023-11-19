import it_IT from 'antd/locale/it_IT.js';

const it = it_IT.default
export const locale = {
    ...it,
    App: {
        runButton: "Esegui",
        debugButton: "Debug",
        cleanButton: "Pulisci",
        cleanConfirm: "Sicuro di cancellare i dati?",
        fullscreenButton: "Fullscreen",
        enableFullscreen: "Abilita schermo intero",
        disableFullscreen: "Disabilita schermo intero",
        filesButton: "File",
        downloadButton: "Scarica",
        downloadTooltip: "Esporta i dati come JSON",
        uploadButton: "Carica",
        uploadTooltip: "Importa i dati come JSON",
        cloudButton: "Server",
        cloudUploadTooltip: "Salva i dati sul server",
        cloudUploadButton: "Salva",
        cloudDownloadTooltip: "Importa i dati dal server",
        cloudDownloadButton: "Importa",
        branchesButton: "Rami",
        autoSavingButton: "AutoSaving",
        autoSavingTooltip: "Disabilita salvataggio automatico",
        autoSaveButton: "AutoSave",
        autoSaveTooltip: "Abilita salvataggio automatico",
        autoSavingErrorTitle: 'Ops... disattivando il salvataggio automatico',
        restoreButton: "Ripristina",
        restoreTooltip: "Ripristina i dati",
        restoreModalTitle: "Ripristina i dati",
        restoreEraseButton: "Cancella memoria",
        restoreCloseButton: "Chiudi",
        restoreCurrent: "corrente",
        restoreRestoreButton: "Ripristina",
        restoreConfirm: "Sicuro di ripristinare i dati?",
        restoreDifferences: "Mostra le differenze rispetto ai dati correnti",
        restoreTitleDifferences: "Differenze"
    },
    Contact: {
        buttonTooltip: "Contatti",
        title: "Contattaci",
        submitButton: "Invia",
        namePlaceholder: "Tuo Nome",
        nameRequired: "Please input your Name!",
        emailPlaceholder: "Email",
        emailRequired: "Inserisci la tua mail!",
        emailInvalid: "Mail invalida!",
        subjectPlaceholder: "Oggetto della mail",
        subjectRequired: "Inserisci l'Oggetto della mail!",
        messagePlaceholder: "Il tuo messaggio",
        messageRequired: "Inserisci il tuo messaggio!",
        errorTitle: 'Ops... qualcosa è andata storta!'
    },
    User: {
        buttonTooltip: "Accedi",
        titleInfo: "Informazioni utente",
        titleLogin: "Login",
        titleLogout: "Sicuro di uscire?",
        titleSetting: "Modifica le impostazioni",
        titleForgot: "Recupera la password",
        titleRegister: "Nuova registrazione",
        titleConfirm: "Invia la mail di conferma",
        titleResetPassword: "Resetta la password",
        loginTooltip: 'Accedi',
        infoButton: 'Profilo',
        settingButton: 'Impostazioni',
        logoutButton: 'Uscire'
    },
    "User.Login": {
        submitButton: "Accedi",
        or: "O",
        registerNow: "registrati ora!",
        emailPlaceholder: "Email",
        emailRequired: "Inserisci la tua mail!",
        emailInvalid: "Mail invalida!",
        sendConfirmMail: "invia nuovamente la mail di conferma",
        passwordPlaceholder: "Password",
        passwordRequired: "Inserisci la tua Password!",
        rememberMe: "Ricordami",
        forgotPassword: "Password dimenticata?",
        errorTitle: 'Ops... qualcosa è andata storta!'
    },
    "User.Logout": {
        submitButton: "Esci",
    },
    "User.Forgot": {
        submitButton: "Recupera la Password",
        or: "O",
        login: "accedi!",
        emailPlaceholder: "Email",
        emailRequired: "Inserisci la tua mail!",
        emailInvalid: "Mail invalida!",
        errorTitle: 'Ops... qualcosa è andata storta!',
    },
    "User.Confirm": {
        submitButton: "Invia le istruzioni",
        or: "O",
        login: "accedi!",
        emailPlaceholder: "Email",
        emailRequired: "Inserisci la tua mail!",
        emailInvalid: "Mail invalida!",
        errorTitle: 'Ops... qualcosa è andata storta!'
    },
    "User.ResetPassword": {
        or: "O",
        login: "accedi!",
        submitButton: "Resetta la password",
        passwordPlaceholder: "Nuova Password",
        passwordRequired: "Inserisci la tua Nuova Password!",
        passwordConfirmPlaceholder: "Conferma la Nuova Password",
        passwordConfirmRequired: "Inserisci nuovamente la tua Nuova Password!",
        passwordConfirmError: 'Le due password che hai inserito non corrispondono!',
        errorTitle: 'Ops... qualcosa è andata storta!'
    },
    "User.Register": {
        submitButton: "Registrati",
        or: "O",
        login: "accedi!",
        emailPlaceholder: "Email",
        emailRequired: "Inserisci la tua mail!",
        emailInvalid: "Mail invalida!",
        firstnamePlaceholder: "Nome",
        firstnameRequired: "Inserisci il tuo Nome!",
        lastnamePlaceholder: "Cognome",
        lastnameRequired: "Inserisci il tuo Cognome!",
        usernamePlaceholder: "Nome utente",
        usernameRequired: "Inserisci il tuo Nome utente!",
        passwordPlaceholder: "Password",
        passwordRequired: "Inserisci la tua Password!",
        passwordConfirmPlaceholder: "Conferma la Password",
        passwordConfirmRequired: "Inserisci nuovamente la tua Password!",
        passwordConfirmError: 'Le due password che hai inserito non corrispondono!',
        errorTitle: 'Ops... qualcosa è andata storta!'
    },
    "User.Setting": {
        errorTitle: 'Ops... qualcosa è andata storta!',
        submitButton: 'Salva',
        revertButton: 'Ripristina',
        firstnamePlaceholder: "Nome",
        firstnameRequired: "Inserisci il tuo Nome!",
        lastnamePlaceholder: "Cognome",
        lastnameRequired: "Inserisci il tuo Cognome!",
    },
    CloudDownloadField: {
        errorTitle: 'Ops... qualcosa è andata storta!',
        fieldErrors: {name: 'Inserisci il nome!'},
        dataSwitchChecked: "corrente",
        dataSwitchUnChecked: "server",
        titleName: "Nome",
        titleData: "Sorgente Dati",
        buttonDownload: "Server",
        buttonOverwrite: "Sovrascrivi",
        createdAt: "Creato",
        updatedAt: "Aggiornato",
        confirmDelete: "Sicuro di eliminare?",
        buttonSaveNew: 'Nuovo record',
        buttonSave: "Salva",
        buttonCancel: "Cancella",
        titleSaveNew: "Salva i dati correnti"
    },
    CloudUploadField: {
        errorTitle: 'Ops... qualcosa è andata storta!',
        fieldErrors: {name: 'Inserisci il nome!'},
        dataSwitchChecked: "corrente",
        dataSwitchUnChecked: "server",
        titleName: "Nome",
        titleData: "Sorgente Dati",
        buttonDownload: "Server",
        buttonOverwrite: "Sovrascrivi",
        createdAt: "Creato",
        updatedAt: "Aggiornato",
        confirmDelete: "Sicuro di eliminare?",
        buttonSaveNew: 'Nuovo record',
        buttonSave: "Salva",
        buttonCancel: "Cancella",
        titleSaveNew: "Salva i dati correnti"
    },
    FileWidget: {
        errorNotUploaded: 'Ops... file non caricato',
        errorFileType: 'Puoi caricare solo file {fileTypes}!',
        errorMaxItems: 'Puoi caricare un massimo di {maxItems} file!',
        errorOnlyOneItem: 'Puoi caricare massimo un file!',
        errorSameFile: 'File {filename} già caricato!',
        dropMessage: 'Trascina il file qui o fai clic per cercare',
        errorToolTip: "Errore di caricamento"
    },
    DebugTemplate: {
        tooltipFloatButton: 'Apri il diagramma di debug',
        titleModal: 'Diagramma di debug'
    },
    Errors: {
        title: "Errori di Validazione"
    },
    ErrorListTemplate: {
        tooltipFloatButton: 'Apri i messaggi di errore',
        descriptionFloatButton: "ERR",
        titleModal: 'Errori'
    },
    PDFField: {
        ...it.Upload, ...it.Image,
        titleSectionSelection: 'Sezioni di stampa'
    },
    ArrayAccordion: {
        ...it.global,
        tooltipExtra: "Copia dati",
        titleCopyButton: 'Seleziona dove copiare i dati?'
    },
    ArrayCopy: {
        ...it.global,
        tooltip: "Copia dati",
        titleCopyButton: 'Seleziona dove copiare i dati?'
    },
    TableField: {
        deleteAllConfirm: "Sei sicuro di eliminare tutti i contenuti?",
        deleteItemConfirm: "Sicuro di eliminare?",
        importTooltip: 'Importa tabella da CSV',
        exportTooltip: "Esporta tabella in CSV",
        addItemTooltip: 'Aggiungi elemento'
    },
    TabsField: {
        clone: 'clona',
        moveup: 'sposta su',
        movedown: 'sposta giù',
        moveleft: 'sposta a sinistra',
        moveright: 'sposta a destra',
        delete: 'cancella',
        select: 'seleziona',
        selectItem: 'Seleziona elemento'
    }
}
export default locale