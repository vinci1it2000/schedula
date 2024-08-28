import {generateWidgets as coreGenerateWidgets} from "../../../core/widgets";
import {generateWidgets as antdGenerateWidgets} from "@rjsf/antd";
import ButtonWidget from "./ButtonWidget";
import CheckboxWidget from './CheckboxWidget'
import DateRangeWidget from './DateRangeWidget'
import DraggerFileUploadWidget from './DraggerFileUploadWidget'
import DraggerFileWidget from './DraggerFileWidget'
import FileUploadWidget from "./FileUploadWidget/core";
import FileWidget from "./FileWidget";
import ImageFileUploadWidget from "./ImageFileUploadWidget";
import ImageFileWidget from "./ImageFileWidget";
import MentionsWidget from "./MentionsWidget";
import RangeWidget from "./RangeWidget";
import RateWidget from "./RateWidget";
import SelectWidget from "./SelectWidget";
import SwitchWidget from "./SwitchWidget";
import TransferWidget from "./TransferWidget";

export function generateWidgets() {
    return {
        ...coreGenerateWidgets(), ...antdGenerateWidgets(),
        ButtonWidget,
        CheckboxWidget,
        DateRangeWidget,
        DraggerFileUploadWidget,
        DraggerFileWidget,
        FileUploadWidget,
        FileWidget,
        ImageFileUploadWidget,
        ImageFileWidget,
        MentionsWidget,
        RangeWidget,
        RateWidget,
        SelectWidget,
        SwitchWidget,
        TransferWidget
    };
}

export default generateWidgets();
