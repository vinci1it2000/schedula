import {
    Accordion,
    AccordionSummary,
    Typography,
    AccordionDetails, Stack
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
                        expandIcon={<ExpandMoreIcon/>}
                        aria-controls="panel1a-content"
                        id="panel1a-header"
                    >
                        <Typography>{(elements[index] || {}).name || ((element.props || {}).schema || {}).title || (element.props || {}).name}</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                        {element}
                    </AccordionDetails>
                </Accordion>
            ))}
        </Stack>

    );
}