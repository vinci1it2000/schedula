import {
    Accordion,
    AccordionSummary,
    Typography,
    AccordionDetails,
    Stack
} from '@mui/material';

import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import React from "react";
import {nanoid} from "nanoid";


export default function _accordion(props) {
    let elements = (props.elements || {}), id = nanoid();
    return (
        <Stack spacing={1} {...props}>
            {props.children.map((element, index) => (
                <Accordion key={index}
                           TransitionProps={{unmountOnExit: true}} {...(elements[index] || {}).props}>
                    <AccordionSummary
                        sx={{"backgroundColor": "lightgray"}}
                        expandIcon={
                            <ExpandMoreIcon/>
                        } aria-controls={id + index + "-content"}
                        id={id + index + "-header"} {...(elements[index] || {}).propsSummary}>
                        <Typography>{(elements[index] || {}).name || ((element.props || {}).schema || {}).title || (element.props || {}).name}</Typography>
                    </AccordionSummary>
                    <AccordionDetails id={id + index + "-details"} {...(elements[index] || {}).propsDetails}>
                        {element}
                    </AccordionDetails>
                </Accordion>
            ))}
        </Stack>
    );
}