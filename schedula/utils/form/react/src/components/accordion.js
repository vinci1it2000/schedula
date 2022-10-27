import {
    Accordion,
    AccordionSummary,
    Typography,
    AccordionDetails,
    Stack
} from '@mui/material';

import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import React from "react";


export default function _accordion(props) {
    let elements = (props.elements || {});
    return (
        <Stack spacing={1} {...props}>
            {props.children.map((element, index) => (
                <Accordion key={index} {...(elements[index] || {}).props}>
                    <AccordionSummary
                        sx={{"backgroundColor": "lightgray"}}
                        expandIcon={
                            <ExpandMoreIcon/>
                        } {...(elements[index] || {}).propsSummary}>
                        <Typography>{(elements[index] || {}).name || ((element.props || {}).schema || {}).title || (element.props || {}).name}</Typography>
                    </AccordionSummary>
                    <AccordionDetails {...(elements[index] || {}).propsDetails}>
                        {element}
                    </AccordionDetails>
                </Accordion>
            ))}
        </Stack>
    );
}