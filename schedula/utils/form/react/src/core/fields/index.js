import ArrayField from './ArrayField';
import BaseField from './BaseField';
import ObjectField from './ObjectField';
import PDFField from './PDFField';
import PlotlyField from './PlotlyField';

export function generateFields() {
    return {
        ArrayField,
        BaseField,
        ObjectField,
        PDFField,
        PlotlyField
    }
}

export default generateFields();