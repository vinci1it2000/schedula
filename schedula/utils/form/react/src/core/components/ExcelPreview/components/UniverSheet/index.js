import '@univerjs/design/lib/index.css';
import '@univerjs/ui/lib/index.css';
import '@univerjs/sheets-ui/lib/index.css';
import '@univerjs/sheets-formula/lib/index.css';
import './index.css';

import {Univer} from '@univerjs/core';
import {defaultTheme} from '@univerjs/design';
import {UniverDocsPlugin} from '@univerjs/docs';
import {UniverDocsUIPlugin} from '@univerjs/docs-ui';
import {UniverFormulaEnginePlugin} from '@univerjs/engine-formula';
import {UniverRenderEnginePlugin} from '@univerjs/engine-render';
import {UniverSheetsPlugin, SheetPermissionService} from '@univerjs/sheets';
import {UniverSheetsUIPlugin} from '@univerjs/sheets-ui';
import {UniverUIPlugin} from '@univerjs/ui';
import {forwardRef, useEffect, useImperativeHandle, useRef} from 'react';
import {LocaleType} from '@univerjs/core';
import {enUS as UniverDesignEnUS} from '@univerjs/design';
import {enUS as UniverDocsUIEnUS} from '@univerjs/docs-ui';
import {enUS as UniverSheetsEnUS} from '@univerjs/sheets';
import {enUS as UniverSheetsUIEnUS} from '@univerjs/sheets-ui';
import {enUS as UniverUIEnUS} from '@univerjs/ui';
import {
    UniverSheetsNumfmtPlugin,
    SetNumfmtCommand
} from '@univerjs/sheets-numfmt';

import {FUniver} from "@univerjs/facade";
import {UniverPermissionService, ICommandService} from '@univerjs/core'

// eslint-disable-next-line react/display-name
const UniverSheet = forwardRef(({data, onCommand, ...props}, ref) => {
            const univerRef = useRef(null);
            const workbookRef = useRef(null);
            const containerRef = useRef(null);

            useImperativeHandle(ref, () => ({
                getData,
            }));

            /**
             * Initialize univer instance and workbook instance
             * @param data {IWorkbookData} document see https://univer.work/api/core/interfaces/IWorkbookData.html
             */
            const init = async (data = {}) => {
                if (!containerRef.current) {
                    throw Error('container not initialized');
                }
                const univer = new Univer({
                    theme: defaultTheme,
                    locale: LocaleType.EN_US,
                    locales: {
                        [LocaleType.EN_US]: {
                            ...UniverSheetsEnUS,
                            ...UniverDocsUIEnUS,
                            ...UniverSheetsUIEnUS,
                            ...UniverUIEnUS,
                            ...UniverDesignEnUS,
                        },
                    }
                });
                univerRef.current = univer;
                const injector = univer.__getInjector();
                const get = injector.get.bind(injector);
                injector.add(SheetPermissionService)


                // core plugins
                univer.registerPlugin(UniverRenderEnginePlugin);
                univer.registerPlugin(UniverFormulaEnginePlugin, {notExecuteFormula: true});
                univer.registerPlugin(UniverUIPlugin, {
                    container: containerRef.current,
                    header: true,
                    footer: true,
                });

                // doc plugins
                univer.registerPlugin(UniverDocsPlugin, {
                    hasScroll: false,
                });
                univer.registerPlugin(UniverDocsUIPlugin);

                // sheet plugins
                univer.registerPlugin(UniverSheetsPlugin, {notExecuteFormula: true});
                univer.registerPlugin(UniverSheetsUIPlugin);
                univer.registerPlugin(UniverSheetsNumfmtPlugin);

                // create workbook instance
                const workbook = univer.createUniverSheet(data);
                workbookRef.current = workbook
                const univerPermissionService = get(UniverPermissionService);
                const sheetPermissionService = get(SheetPermissionService);
                const unitId = workbook.getUnitId()

                univerPermissionService.setEditable(unitId, 0)


                const univerAPI = FUniver.newAPI(univer);

                class DisableEditError extends Error {
                    constructor() {
                        super('editing is disabled')
                        this.name = 'DisableEditError'
                    }
                }


                const commandService = get(ICommandService);
                const cmd = commandService.registerCommand(SetNumfmtCommand)
                const worksheets = workbook.getWorksheets();
                const numFmt = data.numFmt || {}
                for (const [, worksheet] of worksheets) {
                    let sheetId = worksheet.getSheetId()
                    if (numFmt[sheetId]) {
                        workbook.setActiveSheet(worksheet);
                        sheetPermissionService.setSheetEditable(unitId, sheetId, 0)
                        await univerAPI.executeCommand(SetNumfmtCommand.id, {
                            unitId,
                            subUnitId: sheetId,
                            values: numFmt[sheetId]
                        })
                    }
                }
                workbook.setActiveSheet(null);
                cmd.dispose()


                const errListener = (e) => {
                    const error = e instanceof PromiseRejectionEvent ? e.reason : e.error
                    if (error instanceof DisableEditError) {
                        e.preventDefault()
                    }
                }
                window.addEventListener('error', errListener)
                window.addEventListener('unhandledrejection', errListener)
                univerAPI.onCommandExecuted((command) => {
                    if (onCommand)
                        onCommand(command)
                });
                univerAPI.onBeforeCommandExecute((command) => {
                    if ([
                        "sheet.command.move-range",
                        "doc.command.insert-text",
                        "sheet.command.remove-row",
                        "sheet.command.remove-row-confirm",
                        "sheet.command.remove-col",
                        "sheet.command.remove-col-confirm",
                        "sheet.command.delete-range-move-left",
                        "sheet.command.delete-range-move-left-confirm",
                        "sheet.command.delete-range-move-up",
                        "sheet.command.delete-range-move-up-confirm",
                        "sheet.command.clear-selection-content",
                        "sheet.command.clear-selection-format",
                        "sheet.command.clear-selection-all",
                        "univer.command.paste",
                        "sheet.command.paste-value",
                        "sheet.command.paste-format",
                        "sheet.command.paste-col-width",
                        "sheet.command.paste-besides-border",
                        "sheet.command.insert-col",
                        "sheet.command.insert-col-before",
                        "sheet.command.insert-col-after",
                        "sheet.command.insert-row",
                        "sheet.command.insert-row-before",

                        "sheet.command.insert-range-move-right",
                        "sheet.command.insert-range-move-right-confirm",
                        "sheet.command.insert-range-move-down",
                        "sheet.command.insert-range-move-down-confirm",
                        "sheet.mutation.remove-worksheet-merge",
                        "sheet.mutation.set-range-values",
                        "sheet.command.insert-sheet",
                        "doc.command.delete-text",
                        "doc.command.delete-left",
                        "doc.command.delete-right",
                        "sheet.mutation.move-rows",
                        "sheet.mutation.move-cols",
                        "sheet.command.move-rows",
                        "sheet.command.move-cols",
                        "sheet.mutation.remove.numfmt",
                        "sheet.mutation.set.numfmt",
                        "sheet.command.add-worksheet-merge",
                        "sheet.command.add-worksheet-merge-all",
                        "sheet.command.add-worksheet-merge-vertical",
                        "sheet.command.add-worksheet-merge-horizontal",
                        "sheet.command.remove-worksheet-merge",
                        "sheet.command.insert-defined-name",
                        "formula.mutation.set-defined-name",
                        "doc.command-cover-content",
                        "sidebar.operation.defined-name",
                        "sheet.mutation.move-range",
                        "univer.command.cut",
                        "sheet.mutation.add-worksheet-merge",
                        "sheet.command.set-style",
                        "sheet.command.set-bold",
                        "sheet.command.set-range-bold",
                        "sheet.command.set-stroke",
                        "sheet.command.set-range-stroke",
                        "sheet.command.set-underline",
                        "sheet.command.set-range-underline",
                        "sheet.command.set-italic",
                        "sheet.command.set-range-italic",
                        "univer.command.undo",
                        "univer.command.redo",
                        "univer.command.copy",
                        "sheet.command.copy-sheet",
                        "sheet.mutation.insert-sheet",
                        "sheet.command.remove-sheet-confirm",
                        "sheet.command.remove-sheet",
                        "sheet.mutation.remove-sheet",
                        "sheet.operation.rename-sheet",
                        "sheet.command.set-tab-color",
                        "sheet.mutation.set-tab-color",
                        "sheet.command.set-worksheet-hidden",
                        "sheet.mutation.set-worksheet-hidden",
                        "ui-sheet.command.show-menu-list",
                        "sheet.command.set-worksheet-show"
                    ].includes(command.id)) {
                        throw new DisableEditError()
                    } else if ([
                        "sheet.command.move-selection-enter-tab",
                        "sheet.operation.set-cell-edit-visible-arrow",
                        "sheet.command.expand-selection",
                        "sheet.command.hide-row-confirm",
                        "sheet.command.set-row-hidden",
                        "sheet.command.hide-col-confirm",
                        "sheet.command.set-col-hidden",
                        "formula.mutation.set-defined-name-current",
                        "sheet.operation.set-scroll",
                        "sheet.command.set-scroll-relative",
                        "sheet.command.move-selection",
                        "sheet.mutation.set-frozen",
                        "sheet.command.set-frozen",
                        "sheet.mutation.set-worksheet-order",
                        "sheet.command.scroll-view",
                        "sheet.operation.set-selections",
                        "doc.operation.set-selections",
                        "sheet.command.set-worksheet-activate",
                        "sheet.operation.set-activate-cell-edit",
                        "sheet.operation.set-worksheet-active",
                        "sheet.operation.set-cell-edit-visible",
                    ].includes(command.id)) {
                    } else {
                        console.log(command)
                    }
                })
            };

            /**
             * Destroy univer instance and workbook instance
             */
            const destroyUniver = () => {
                univerRef.current?.dispose();
                univerRef.current = null;
                workbookRef.current = null;
            };

            /**
             * Get workbook data
             */
            const getData = () => {
                if (!workbookRef.current) {
                    throw new Error('Workbook is not initialized');
                }
                return workbookRef.current.save();
            };

            useEffect(() => {
                init(data);
                return () => {
                    destroyUniver();
                };
            }, [data]);

            return <div ref={containerRef} className="univer-preview univer-container"/>
        }
    )
;

export default UniverSheet;