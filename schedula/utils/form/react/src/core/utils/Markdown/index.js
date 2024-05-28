import nunjucks from 'nunjucks';
import {markdownTable} from 'markdown-table'
import isObject from "lodash/isObject";
import isArray from "lodash/isArray"
import get from "lodash/get"
import has from "lodash/has"

var env = new nunjucks.Environment();
env.addFilter('decimal', function (val, i, lang) {
    let n = i ? Math.pow(10, i) : 1;
    return (Math.round((val + Number.EPSILON) * n) / n).toLocaleString(lang || 'it');
});
env.addFilter('locale', function (val, lang) {
    return (val).toLocaleString(lang || 'it');
});
env.addFilter('n', function (val, lang, options) {
    return String(new Intl.NumberFormat(lang.replace('_', '-'), {
        minimumFractionDigits: 0,
        maximumFractionDigits: 20,
        ...options
    }).format(val))
});
env.addFilter('table', function (val, header, kw = {}) {
    let {
        empty = ' ',
        footerEmpty = ' ',
        footer = false,
        removeEmpty = false,
        format,
        footerFormat,
        ...options
    } = kw
    try {
        if (!Array.isArray(val)) {
            console.log(`Error in rendering table: wrong type ${typeof val}`)
            return null
        }
        let headerMap = {}
        if (header) {
            header = header.map(k => {
                if (Array.isArray(k)) {
                    headerMap[k[0]] = k[1]
                    return k[0]
                } else {
                    headerMap[k] = k
                    return k
                }
            })
        }

        if (footerFormat === true) {
            footerFormat = format
        }
        if (!header) {
            header = new Set(val.reduce((a, v) => [...a, ...Object.keys(v)], []))
            header = Array.from(header).sort()
            header.forEach(k => {
                headerMap[k] = k
            })
        } else if (removeEmpty) {
            let keys = val.reduce((a, v) => [...a, ...Object.keys(v)], [])
            if (footer && footer !== true && !Array.isArray(footer)) {
                Object.keys(footer).forEach(k => {
                    keys.push(k)
                })
                footer = header.map(k => get(footer, k, footerEmpty))
            }
            keys = new Set(keys)
            let mask = header.map(k => keys.has(k))
            header = header.filter((k, i) => mask[i])

            if (Array.isArray(footer)) {
                footer = footer.filter((k, i) => mask[i])
            }
        }
        if (format) {
            let defaultFormat = get(format, 'DEFAULT')
            val = val.map(d => (header.map(k => {
                if ((defaultFormat || has(format, k)) && has(d, k)) {
                    let func = get(format, k, defaultFormat)
                    if (Array.isArray(func)) {
                        return func[0](d[k], func[1])
                    } else if (func) {
                        return func(d[k])
                    }
                }
                return get(d, k, empty)
            })))
        } else {
            val = val.map(d => (header.map(k => (get(d, k, empty)))))
        }

        if (footer === true) {
            footer = val[val.length - 1]
            val = val.slice(0, -1)
        } else if (footer && footerFormat) {
            let defaultFormat = get(footerFormat, 'DEFAULT')
            footer = footer.map((v, i) => {
                let k = header[i]
                if ((defaultFormat || has(footerFormat, k)) && v !== footerEmpty) {
                    let func = get(footerFormat, k, defaultFormat)
                    if (Array.isArray(func)) {
                        return func[0](v, func[1])
                    } else {
                        return func(v)
                    }
                }
                return v
            })

        }
        let table = markdownTable([header.map(k => headerMap[k]), ...val], options);
        if (footer) {
            table = table + '\n' + markdownTable([footer], options)
        }
        return table;
    } catch (e) {
        console.log(`Error in rendering table: data ${e}`)
        throw e
    }
});


function format2(string, args = [], kwargs = {}) {
    let i = -1;
    return string.replace(/{(\d+)}/g, function (match, number) {
        return typeof args[number] != 'undefined' ? args[number] : match;
    }).replace(/{(\w[^}]*)}/g, function (match, key) {
        return typeof kwargs[key] != 'undefined' ? kwargs[key] : match;
    }).replace(/{(\s*)}/g, function (match) {
        i++;
        return typeof args[i] != 'undefined' ? args[i] : match;
    });
}

export default function formatMd({children, formData, ...props}) {
    let args = [], kwargs = {}, data = formData || {};
    if (!isObject(data)) {
        args = [data]
    } else if (isArray(data)) {
        args = data
    } else {
        kwargs = data
    }
    if (isArray(children))
        children = children.join('')
    try {
        return format2(env.renderString(children, {
            data,
            props,
            window
        }), args, kwargs);

    } catch (e) {
        console.log(`Error in formatting md ${children}`)
        console.log(e)
        return null
    }

}