import isString from "lodash/isString";
import get from "lodash/get";
import isArray from "lodash/isArray";
import assign from "lodash/assign";

export default function getStyle(style, styles) {
    if (isString(style)) {
        return get(styles, style)
    } else if (isArray(style)) {
        return assign({}, ...style.map(v => (getStyle(v, styles))))
    } else {
        return style || {}
    }
}