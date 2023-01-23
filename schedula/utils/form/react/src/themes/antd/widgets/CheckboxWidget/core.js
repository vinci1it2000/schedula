import React from "react";
import {Checkbox} from "antd";
import {ariaDescribedByIds, labelValue} from "@rjsf/utils";

export default function CheckboxWidget(props) {
    const {
        autofocus,
        disabled,
        formContext,
        id,
        label,
        hideLabel,
        onBlur,
        onChange,
        onFocus,
        options,
        readonly,
        value,
    } = props;
    const {readonlyAsDisabled = true} = formContext;

    const handleChange = ({target}) =>
        onChange(target.checked);

    const handleBlur = ({target}) =>
        onBlur(id, target.checked);

    const handleFocus = ({target}) =>
        onFocus(id, target.checked);

    const extraProps = {
        onBlur: !readonly ? handleBlur : undefined,
        onFocus: !readonly ? handleFocus : undefined,
    };

    return (
        <Checkbox
            autoFocus={autofocus}
            checked={typeof value === "undefined" ? false : value}
            disabled={disabled || (readonlyAsDisabled && readonly)}
            id={id}
            name={id}
            onChange={!readonly ? handleChange : undefined}
            {...extraProps}
            aria-describedby={ariaDescribedByIds(id)}>
            {labelValue(options.hasOwnProperty('label') ? options.label : label, hideLabel, '')}
        </Checkbox>
    );
}