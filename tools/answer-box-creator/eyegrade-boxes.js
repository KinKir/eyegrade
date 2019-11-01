document.addEventListener('DOMContentLoaded', function(event) {
    draw_answer_box();
})

var draw_answer_box = function() {
    var canvas = document.getElementById('answer_box');
    var drawing = new AnswerBoxesDrawingContext(canvas, 20, 4);
    drawing.draw("A");
}

var AnswerBoxesDrawingContext = function(canvas, num_questions, num_choices) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.boxes = new AnswerBoxes(num_questions, num_choices);

    this.draw = function(model_letter) {
        this.boxes.draw(this.ctx, model_letter);
    }

    this.clear = function() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }
}

var AnswerBoxes = function(num_questions, num_choices) {
    this.geometry = GeometryAnalyzer.best_geometry(num_questions, num_choices);

    this.draw = function(ctx, model_letter) {
        var cell_size = GeometryAnalyzer.cell_size(this.geometry, ctx.canvas.width, ctx.canvas.height);
        var top_left_corner = GeometryAnalyzer.top_left_corner(this.geometry, cell_size, ctx.canvas.width, ctx.canvas.height);
        var num_digits_question_num = ~~(1 + (this.geometry.num_questions - 1) / 10);
        var first_question_number = 1;
        var infobits = this.infobits(model_letter);
        for (var i = 0; i < this.geometry.num_tables; i++) {
            var extra_bottom_line = this.geometry.questions_per_table[i] < this.geometry.num_rows;
            var box = new AnswerBox(this.geometry.questions_per_table[i], num_choices, first_question_number, num_digits_question_num, extra_bottom_line);
            var box_top_left_corner = {
                x: top_left_corner.x + i * (num_choices + 1) * cell_size.width,
                y: top_left_corner.y
            };
            var infobits_fragment = infobits.substring(i * num_choices, (i + 1) * num_choices);
            box.draw(ctx, box_top_left_corner, cell_size, infobits_fragment);
            first_question_number += this.geometry.questions_per_table[i];
        }
    }

    this.infobits = function(model_letter) {
        var base_code = this.infobits_table[model_letter.charCodeAt(0) - 65];
        var code = base_code;
        while (code.length < this.geometry.num_columns) {
            code += base_code;
        }
        return code.substring(0, this.geometry.num_columns);
    }

    this.infobits_table = [
        "DDDU",
        "UDDD",
        "DUDD",
        "UUDU",
        "DDUD",
        "UDUU",
        "DUUU",
        "UUUD"
    ]
}

var AnswerBox = function(num_questions, num_choices, first_question_number, num_digits_question_num, extra_bottom_line) {
    this.num_questions = num_questions;
    this.num_choices = num_choices;
    this.first_question_number = first_question_number;
    this.num_digits_question_num = num_digits_question_num;
    this.extra_bottom_line = extra_bottom_line;

    this.draw = function(ctx, top_left_corner, cell_size, infobits_fragment) {
        var bottom_right_corner = {
            x: top_left_corner.x + (this.num_choices + 1) * cell_size.width,
            y: top_left_corner.y + (this.num_questions + 3) * cell_size.height
        }
        var left_x = top_left_corner.x + cell_size.width;
        var right_x = left_x + cell_size.width * this.num_choices;
        var top_y = top_left_corner.y + cell_size.height;
        var bottom_y = top_y + cell_size.height * this.num_questions;
        this.draw_lines(ctx, cell_size, left_x, right_x, top_y, bottom_y);
        this.debug_draw_frame(ctx, top_left_corner, bottom_right_corner);
        this.draw_question_numbers(ctx, cell_size, top_left_corner);
        this.draw_choice_letters(ctx, cell_size, top_left_corner);
        this.draw_infobits(ctx, cell_size, top_left_corner, infobits_fragment);
    }

    this.draw_lines = function(ctx, cell_size, left_x, right_x, top_y, bottom_y) {
        ctx.beginPath();
        // Draw vertical lines:
        for (var i = 0; i < this.num_choices + 1; i++) {
            var x = left_x + i * cell_size.width;
            ctx.moveTo(x, top_y);
            ctx.lineTo(x, bottom_y);
        }
        // Draw horizontal lines
        var num_lines;
        if (!this.extra_bottom_line) {
            num_lines = this.num_questions + 1;
        } else {
            // Extra line because other boxes have one row more
            num_lines = this.num_questions + 2;
        }
        for (var i = 0; i < num_lines; i++) {
            var y = top_y + i * cell_size.height;
            ctx.moveTo(left_x, y);
            ctx.lineTo(right_x, y);
        }
       ctx.stroke();
    }

    this.draw_question_numbers = function(ctx, cell_size, top_left_corner) {
        var font_size = this.font_size(cell_size);
        ctx.textAlign = "right";
        ctx.font = font_size + "px sans-serif";
        var offset = {
            x: ~~(0.9 * cell_size.width),
            y: ~~(0.9 * cell_size.height)
        }
        for (var i = 1; i <= this.num_questions; i++) {
            var question_num = this.first_question_number + i - 1;
            var x = top_left_corner.x + offset.x;
            var y = top_left_corner.y + offset.y + cell_size.height * i;
            ctx.fillText(question_num.toString(), x, y, 0.8 * cell_size.width);
        }
    }

    this.draw_choice_letters = function(ctx, cell_size, top_left_corner) {
        var font_size = this.font_size(cell_size);
        ctx.textAlign = "center";
        ctx.font = font_size + "px sans-serif";
        var offset = {
            x: ~~(0.5 * cell_size.width),
            y: ~~(0.9 * cell_size.height)
        }
        for (var i = 1; i <= this.num_choices; i++) {
            var letter_num = 64 + i; // i=1 for 'A'
            var x = top_left_corner.x + offset.x + cell_size.width * i;
            var y = top_left_corner.y + offset.y;
            ctx.fillText(String.fromCharCode(letter_num), x, y, 0.8 * cell_size.width);
        }
    }

    this.debug_draw_frame = function(ctx, top_left_corner, bottom_right_corner) {
        var previous_style = ctx.strokeStyle;
        ctx.strokeStyle = "red";
        ctx.beginPath();
        ctx.moveTo(top_left_corner.x, top_left_corner.y);
        ctx.lineTo(bottom_right_corner.x, top_left_corner.y);
        ctx.lineTo(bottom_right_corner.x, bottom_right_corner.y);
        ctx.lineTo(top_left_corner.x, bottom_right_corner.y);
        ctx.lineTo(top_left_corner.x, top_left_corner.y);
        ctx.stroke();
        ctx.strokeStyle = previous_style;
    }

    this.draw_infobits = function(ctx, cell_size, top_left_corner, infobits_fragment) {
        var y_up = ~~(top_left_corner.y + (this.num_questions + 1) * cell_size.height + 0.2 * cell_size.height);
        var y_down = y_up + cell_size.height;
        var size = ~~(0.6 * cell_size.height);
        var x_base = ~~(top_left_corner.x + (cell_size.width - size) / 2);
        for (var i = 0; i < this.num_choices; i++) {
            var x = x_base + (i + 1) * cell_size.width;
            var y;
            if (infobits_fragment.charAt(i) === "U") {
                y = y_up;
            } else {
                y = y_down;
            }
            ctx.fillRect(x, y, size, size);
        }
    }

    this.font_size = function(cell_size) {
        var size_for_width = ~~(cell_size.width / this.num_digits_question_num);
        var size_for_height = cell_size.height;
        return Math.min(size_for_width, size_for_height);
    }
}

var GeometryAnalyzer = {
    // default cell aspect ratio: cell width / cell height = 1.5
    default_cell_ratio: 1.5,

    best_geometry: function(num_questions, num_choices) {
        var geometries = [];
        for (var i = 1; i < 5; i++) {
            geometries.push(this.fit(num_questions, num_choices, i));
        }
        return this.choose_geometry(geometries);
    },

    cell_size: function(geometry, canvas_width, canvas_height) {
        var usable_width = 0.95 * canvas_width; // 2.5% left and right margins
        var usable_height = 0.95 * canvas_height; // 2.5% top and bottom margin
        var cell_width = ~~(usable_width / geometry.total_columns);
        var cell_height = ~~(cell_width / geometry.cell_ratio);
        if (cell_height * geometry.total_rows > usable_height) {
            cell_height = ~~(usable_height / geometry.total_rows);
            cell_width = ~~(cell_height * geometry.cell_ratio);
        }
        return {
            width: cell_width,
            height: cell_height
        };
    },

    top_left_corner: function(geometry, cell_size, canvas_width, canvas_height) {
        return {
            x: ~~((canvas_width - cell_size.width * geometry.total_columns) / 2),
            y: ~~((canvas_height - cell_size.height * geometry.total_rows) / 2)
        };
    },

    fit: function(num_questions, num_choices, num_tables) {
        var g = {};
        g.num_questions = num_questions;
        g.num_choices = num_choices;
        g.num_tables = num_tables;
        g.questions_per_table = this.questions_per_table(num_questions, num_tables);
        g.num_rows = Math.max(...g.questions_per_table);
        g.num_columns = num_tables * num_choices;
        g.total_rows = g.num_rows + 3; // header line + 2 infobits lines
        g.total_columns = g.num_columns + num_tables; // one question number per table
        var actual_ratio = this.default_cell_ratio * g.num_columns / g.num_rows;
        // no dimension should be more than 30% larger than the other
        if (actual_ratio > 1.3) {
            // Cells are too wide
            g.cell_ratio = 1.3 * g.num_rows / g.num_columns;
        } else if (actual_ratio < 0.769) {
            // Cells are too heigh
            g.cell_ratio = 0.769 * g.num_rows / g.num_columns;
        } else {
            // The default aspect ratio works fine
            g.cell_ratio = this.default_cell_ratio;
        }
        return g;
    },

    questions_per_table: function(num_questions, num_tables) {
        var questions_per_table = []
        var q = ~~(num_questions / num_tables)
        var remainder = num_questions % num_tables
        for (var i = 0; i < num_tables; i++) {
            if (remainder > 0) {
                questions_per_table.push(q + 1);
                remainder--;
            } else {
                questions_per_table.push(q);
            }
        }
        return questions_per_table;
    },

    choose_geometry: function(geometries) {
        var i;
        var best_dist = Infinity;
        var best_geometry;
        for (i in geometries) {
            g = geometries[i];
            dist = Math.abs(g.cell_ratio - this.default_cell_ratio)
            if (dist < best_dist) {
                best_dist = dist;
                best_geometry = g;
            } else {
                // Ratios go from higher to lower values.
                // Once a geometry is farther away from the default than the previous one,
                // iteration can stop.
                break;
            }
        }
        return best_geometry;
    }
}