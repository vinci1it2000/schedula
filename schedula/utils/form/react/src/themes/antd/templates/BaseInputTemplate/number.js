import {useMemo, useState} from "react";
import {InputNumber} from 'antd';
import {useLocaleStore} from "../../models/locale";


export default function InputNumberTemplate(
    {format, value, id, emptyValue, onBlur, onFocus, ...props}) {
    const [focused, setFocused] = useState(false)
    const {getLocale} = useLocaleStore()
    const locale = getLocale('language').replace("_", "-")

    const {key, numberParser, numberFormatter} = useMemo(() => {
        const group = new Intl.NumberFormat(locale).format(1111).replace(/1/g, "");
        const decimal = new Intl.NumberFormat(locale).format(1.1).replace(/1/g, "");
        let numberFormatter
        if (focused) {
            numberFormatter = (value) => (value.replace(new RegExp("\\.", "g"), decimal))
        } else {
            numberFormatter = (value) => {
                if (value)
                    return new Intl.NumberFormat(locale, {
                        minimumFractionDigits: 0,
                        maximumFractionDigits: 20,
                        ...format
                    }).format(value);
                return ""
            };
        }
        const numberParser = val => {
            if (val || val === 0) {
                let reversedVal = val.replace(new RegExp("\\" + group, "g"), "");
                reversedVal = reversedVal.replace(new RegExp("\\" + decimal, "g"), ".");
                reversedVal = reversedVal.replace(/[^0-9.-]/g, "")
                return reversedVal;
            } else {
                return emptyValue
            }
        };
        return {
            key: `${id}-${locale}`,
            numberParser,
            numberFormatter
        }
    }, [id, locale, format, emptyValue, focused])
    const handleBlur = (arg) => {
        setFocused(false)
        if (onBlur)
            onBlur(arg)
    };

    const handleFocus = (arg) => {
        setFocused(true)
        if (onFocus)
            onFocus(arg)
    };
    return <InputNumber
        key={key}
        id={id}
        onFocus={handleFocus}
        onBlur={handleBlur}
        formatter={numberFormatter}
        parser={numberParser}
        value={value}
        {...props}
    />
}