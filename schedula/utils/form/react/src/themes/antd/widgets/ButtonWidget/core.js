import React from "react";
import {Button} from "antd";
import {ariaDescribedByIds, labelValue} from "@rjsf/utils";

export default function ButtonWidget(props) {
    const {
        autofocus,
        disabled,
        formContext,
        id,
        label,
        hideLabel,
        onChange,
        options,
        readonly,
        value,
    } = props;
    const {readonlyAsDisabled = true} = formContext;
    const {editValue} = options;
    return (
        <Button
            autoFocus={autofocus}
            disabled={disabled || (readonlyAsDisabled && readonly)}
            id={id}
            name={id}
            onClick={!readonly ? () => {
                onChange(editValue(value))
            } : undefined}
            aria-describedby={ariaDescribedByIds(id)}>
            {labelValue(options.hasOwnProperty('label') ? options.label : label, hideLabel, '')}
        </Button>
    );
}