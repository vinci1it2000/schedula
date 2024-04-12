import {CellValueType} from "@univerjs/core";
import {ValueType, Workbook} from "exceljs";
import hash from "object-hash";

function dateToExcel(d, date1904) {
    // eslint-disable-next-line no-mixed-operators
    return 25569 + d.getTime() / (24 * 3600 * 1000) - (date1904 ? 1462 : 0);
}

function getStyle(cell) {
    let styles = {}
    const {font = {}, alignment = {}, fill = {}, border = {}} = cell;
    if (font.bold) styles.bl = 1;
    if (font.italic) styles.it = 1;
    if (font.strike) styles.st = 1;
    if (font.family) styles.ff = font.name
    if (font.size) styles.fs = font.size
    if (font.underline) styles.ul = 1;
    if (font.outline) styles.ol = 1;
    if (font.color && font.color.argb) styles.cl = {rgb: `#${font.color.argb.slice(2)}`}
    if (font.vertAlign === 'superscript') styles.va = 3
    if (font.vertAlign === 'subscript') styles.va = 2

    if (alignment.vertical === 'top') styles.vt = 1
    if (alignment.vertical === 'middle') styles.vt = 2
    if (alignment.vertical === 'bottom') styles.vt = 3

    if (alignment.horizontal === 'left') styles.ht = 1
    if (alignment.horizontal === 'center') styles.ht = 2
    if (alignment.horizontal === 'right') styles.ht = 3
    if (alignment.horizontal === 'justify') styles.ht = 4

    if (alignment.wrapText && alignment.wrapText) styles.tb = 3
    if (alignment.wrapText && !alignment.wrapText) styles.tb = 1

    if (alignment.textRotation) {
        styles.tr = alignment.textRotation === 'vertical' ? {v: 1} : {a: alignment.textRotation}
    }

    if (alignment.readingOrder === 'ltr') styles.td = 1
    if (alignment.readingOrder === 'rtl') styles.td = 2

    if (fill.type === "pattern") {
        const {fgColor, bgColor} = fill;
        if (fgColor && fgColor.argb) {
            styles.bg = {rgb: `#${fgColor.argb.slice(2)}`}
        } else if (bgColor && bgColor.argb) {
            styles.bg = {rgb: `#${fgColor.argb.slice(2)}`}
        }
    }
    if (border) {
        let border_map = [
            ['top', 't'],
            ['bottom', 'b'],
            ['left', 'l'],
            ['right', 'r']
        ]
        if (border.diagonal) {
            if (border.diagonal.up) {
                border_map.push(['diagonal', 'tl_br'])
            }
            if (border.diagonal.down) {
                border_map.push(['diagonal', 'bl_tr'])
            }
        }
        border_map.forEach(([i, j]) => {
            let _border = border[i]
            if (_border) {
                if (!styles.bd) styles.bd = {}
                styles.bd[j] = {
                    s: {
                        'dashed': 4,
                        'dashDot': 5,
                        'dashDotDot': 6,
                        'dotted': 3,
                        'double': 7,
                        'hair': 2,
                        'medium': 8,
                        'mediumDashed': 9,
                        'mediumDashDot': 10,
                        'mediumDashDotDot': 11,
                        'slantDashDot': 12,
                        'thin': 1,
                        'thick': 13
                    }[_border.style],
                    cl: (_border.color && _border.color.argb) ? `#${_border.color.argb.slice(2)}` : undefined
                }
            }
        })
    }
    return styles
}


const _re_n = new RegExp("\n", 'gi')

function genCellTextByType(cell, date1904, styles) {
    let {type, value} = cell;
    let res = {}, style = getStyle(cell)

    if (Object.keys(style).length) {
        res.s = style
        res.v = ' '
        res.t = CellValueType.FORCE_STRING
    }
    if (type === ValueType.Hyperlink) {
        value = value.text
        if (value.richText) {
            type = ValueType.RichText
        } else {
            type = ValueType.String
        }
    }
    switch (type) {
        case ValueType.Null:
            res.v = ''
            res.t = CellValueType.STRING
            break
        case ValueType.RichText:
            let dataStream = "", st = 0, ed, ts, textRuns = [];
            for (const rich of value.richText) {
                ed = st + rich.text.length
                ts = getStyle(rich)
                if (Object.keys(ts).length) {
                    textRuns.push({st, ed, ts})
                }
                dataStream += rich.text;
                st = ed
            }
            dataStream = dataStream.replace(_re_n, '\r') + "\r\n"
            res.p = {
                body: {
                    dataStream, textRuns,
                    paragraphs: [...(dataStream + '\n').matchAll(_re_n)].map(a => ({
                        startIndex: a.index
                    })),
                    sectionBreaks: [{startIndex: dataStream.length - 1}]
                }
            }
            break
        case ValueType.Formula:
            res.v = cell.result
            res.f = cell.formula
            if (typeof res.v === 'number') {
                res.t = CellValueType.NUMBER
            } else if (typeof res.v === 'boolean') {
                res.t = CellValueType.BOOLEAN
            } else if (typeof res.v === 'string') {
                res.t = CellValueType.STRING
            } else if (typeof res.v === 'object') {
                res.v = dateToExcel(res.v, date1904)
                res.t = CellValueType.NUMBER
            } else {
                res.t = CellValueType.NUMBER
            }

            break
        case ValueType.Date:
            res.v = dateToExcel(value, date1904)
            res.t = CellValueType.NUMBER
            break
        case ValueType.Boolean:
            res.v = value
            res.t = CellValueType.BOOLEAN
            break
        case ValueType.Number:
            res.v = value
            res.t = CellValueType.NUMBER
            break
        case ValueType.String:
            const indexes = [...(value + '\n').matchAll(_re_n)].map(a => a.index);
            if (indexes.length > 1) {
                res.p = {
                    body: {
                        dataStream: value.replace(_re_n, '\r') + '\r\n',
                        textRuns: [{st: 0, ed: value.length}],
                        paragraphs: indexes.map(startIndex => ({
                            startIndex
                        })),
                        sectionBreaks: [{startIndex: value.length + 1}]
                    }
                }
            } else {
                res.v = value
                res.t = CellValueType.STRING
            }

            break
        default:
            res.v = value
            res.t = CellValueType.FORCE_STRING
            break
    }
    if (res.s) {
        const styleHash = hash(res.s, {
            'algorithm': 'sha1',
            'encoding': 'base64'
        })
        styles[styleHash] = res.s
        res.s = styleHash
    }
    return res
}

function computeRangeAddress(cell) {
    const {row, col} = cell.fullAddress;
    // find the next merged cell
    let nextRow = row;
    let nextCell;
    do {
        nextRow++
        nextCell = cell.worksheet.findCell(nextRow, col);
    } while (nextCell && nextCell.master === cell);
    let nextCol = col;
    nextCell = undefined;
    do {
        nextCol++
        nextCell = cell.worksheet.findCell(row, nextCol);
    } while (nextCell && nextCell.master === cell);
    return {
        startRow: row - 1,
        startColumn: col - 1,
        endRow: nextRow - 2,
        endColumn: nextCol - 2
    }
}

export default async function xtos(url) {
    const wb = new Workbook();
    const file = await (await fetch(url)).arrayBuffer()
    await wb.xlsx.load(file, {
        ignoreNodes: [
            'dataValidations', 'sheetProtection', 'conditionalFormatting',
            'picture', 'drawing'
        ],
    });
    const sheetsLen = wb.worksheets.length;
    let res = {
        sheets: {},
        sheetOrder: [],
        styles: {},
        numFmt: {}
    };
    const date1904 = wb.properties.date1904

    for (let idx = 0; idx < sheetsLen; idx++) {
        res.sheetOrder.push(String(idx))
        const ws = wb.worksheets[idx];
        let numFmts = []
        let o = {
            name: ws.name,//Worksheet name
            tabColor: ws.properties.tabColor || "",//Worksheet color
            id: String(idx),//Worksheet id
            status: idx === 0 ? 1 : 0, //Worksheet active status
            hidden: 0,//Whether worksheet hide
            defaultRowHeight: 24, //Customized default row height
            defaultColWidth: 72, //Customized default column width
            rowCount: ws.rowCount, //the number of rows in a sheet
            columnCount: ws.columnCount,//the number of columns in a sheet
            cellData: {},//Initial the cell data
            mergeData: [],
            rowData: [],
            columnData: []
        };
        const curDefaultRowHeight = ws.properties.defaultRowHeight || 15;

        ws.eachRow({includeEmpty: true}, (row, rowNumber) => {
                let r = {}
                o.cellData[rowNumber - 1] = r
                if (row.height)
                    o.rowData.push({h: row.height * 24 / curDefaultRowHeight})
                row.eachCell({includeEmpty: true}, (cell, colNumber) => {
                        if (!(cell.isMerged && cell.master !== cell)) {
                            if (cell.isMerged) {
                                o.mergeData.push(computeRangeAddress(cell))
                            }
                            r[colNumber - 1] = genCellTextByType(cell, date1904, res.styles)
                            let numFmt = cell.numFmt
                            if (numFmt) {
                                numFmts.push({
                                    pattern: numFmt,
                                    row: rowNumber - 1,
                                    col: colNumber - 1
                                })
                            }
                        } else {
                            r[colNumber - 1] = {
                                s: o.cellData[cell.master.row - 1][cell.master.col - 1].s
                            }
                        }
                    }
                )
            }
        )
        const curDefaultColWidth = ws.properties.defaultColWidth || 9;

        for (let j = 1; j <= ws.columnCount; j++) {
            const column = ws.getColumn(j);
            o.columnData.push({
                w: !column.width ? 72 : (column.width * 72) / curDefaultColWidth
            })
        }
        if (numFmts.length)
            res.numFmt[idx] = numFmts
        res.sheets[idx] = o;
    }

    return res;
}